from __future__ import annotations
from typing import TYPE_CHECKING

import io
import os
import shutil
import asyncio
import hashlib
import platform

from pathlib import Path
from collections import deque
from dotenv import load_dotenv
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from redis.commands.json.path import Path as RedisPath

from fastapi import APIRouter, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, StreamingResponse

from playwright.async_api import async_playwright, Error as PlaywrightError

from hypercorn.asyncio import serve as hypercorn_serve
from hypercorn.config import Config as HypercornConfig

from _orjson import ORJSONDecoder, ORJSONEncoder
from models import Mr_convert, Mr_convert_status, Mr_get_video
from errors import InvalidURLError, PageNotFoundError, SiteDownError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator as TAsyncGenerator

    from type import T_PubSubHandler_message, TRedisLocks, TRouteMap


load_dotenv("./.env")

Path("videos").mkdir(exist_ok=True)

if platform.system == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class BrowserController:
    def __init__(self, webserver: WebServer) -> None:
        self.webserver = webserver

        self.playwright = None
        self.browser = None

    async def initialize(self) -> None:
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

    async def existing_recording(
        self, id: str, *, get_buffer: bool = True
    ) -> io.BytesIO | str | None:
        async with self.webserver.redis.locks["videos_json"]:
            resp = await self.webserver.redis.json.get(f"videos:{id}")

        if resp and resp["status"] == "ready":
            rel_path = resp["path"]

            dir_exists = os.path.isdir(Path(rel_path).parent)
            if dir_exists:
                if len(videos := os.listdir(rel_path)) == 1:
                    video_path = f"{rel_path}/{videos[0]}"

                    if get_buffer:
                        with open(video_path, "rb") as f:
                            data = f.read()
                            buffer = io.BytesIO(data)

                        return buffer
                    else:
                        return video_path
            else:
                async with self.webserver.redis.locks["videos_json"]:
                    await self.webserver.redis.json.delete(f"videos:{id}")

        return None

    async def record(
        self,
        id: str,
        url: str,
        *,
        speed: int = 300,
        get_buffer: bool = True,
        delete_from_filesystem: bool = False,
    ) -> io.BytesIO | str:
        if get_buffer is False and delete_from_filesystem is True:
            raise Exception(
                "Invalid combination of parameters found.\n"
                "get_buffer must be set to True for delete_from_filesystem to be True"
            )

        video_dir = f"videos/{id}"

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            screen={"width": 1920, "height": 1080},
            record_video_dir=video_dir,
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        cdp = await context.new_cdp_session(page)

        try:
            response = await page.goto(url)
            if response.status == 500:
                raise SiteDownError()
            elif response.status == 404:
                raise PageNotFoundError()
        except PlaywrightError as e:
            if "ERR_NAME_NOT_RESOLVED" in e.message:
                raise InvalidURLError()

        height = await page.evaluate(
            "() => (document.documentElement.scrollHeight || document.body.scrollHeight) - window.innerHeight"
        )

        async with self.webserver.redis.locks["videos_json"]:
            await self.webserver.redis.json.merge(
                f"videos:{id}",
                RedisPath.root_path(),
                {
                    "status": "recording",
                },
            )

        await cdp.send(
            "Input.synthesizeScrollGesture",
            {
                "x": 0,
                "y": 0,
                "yDistance": -height,
                "speed": speed,
            },
        )

        await cdp.detach()
        await page.close()
        await context.close()

        async with self.webserver.redis.locks["videos_json"]:
            await self.webserver.redis.json.merge(
                f"videos:{id}",
                RedisPath.root_path(),
                {"status": "processing"},
            )

        video_name = os.listdir(video_dir)[0]
        rel_path = f"{video_dir}/{video_name}"

        if get_buffer:
            with open(rel_path, "rb") as f:
                data = f.read()
                buffer = io.BytesIO(data)

            if delete_from_filesystem:
                shutil.rmtree(rel_path)

            return buffer
        else:
            return rel_path

    async def close(self) -> None:
        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()


class RedisHandler:
    def __init__(self, webserver: WebServer, url: str) -> None:
        self.client = aioredis.from_url(url)
        self.webserver = webserver

        self.pubsub = self.client.pubsub()
        self.json = self.client.json(encoder=ORJSONEncoder(), decoder=ORJSONDecoder())

        self.locks: TRedisLocks = {
            "new_task": self.client.lock("new_task"),
            "videos_json": self.client.lock("videos_json"),
        }

        self.tasks: list[asyncio.Task] = []

        self.req_queue = deque()

    async def initialize(self) -> None:
        await self.pubsub.subscribe(**{"new_task": self.listen_for_new_tasks})

        t_pubsub_listener = asyncio.create_task(self.pubsub_listener())
        self.tasks.append(t_pubsub_listener)

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()

        await self.client.aclose()

    async def pubsub_listener(self) -> None:
        while True:
            await self.pubsub.get_message(ignore_subscribe_messages=True)
            await asyncio.sleep(0.001)

    async def listen_for_new_tasks(self, message: T_PubSubHandler_message) -> None:
        async with self.locks["new_task"]:
            id = message["data"].decode()

        existing_rec: str | None = await self.webserver.browser_cont.existing_recording(
            id, get_buffer=False
        )

        if existing_rec:
            file_path = existing_rec
        else:
            async with self.locks["videos_json"]:
                response: dict = await self.json.get(f"videos:{id}")

            self.req_queue.append(f"videos:{id}")

            url: str = response.get("url")
            path = await self.webserver.browser_cont.record(
                id, url, get_buffer=False, speed=300
            )
            file_path = path

            self.req_queue.remove(f"videos:{id}")

        async with self.locks["videos_json"]:
            await self.json.merge(
                f"videos:{id}",
                RedisPath.root_path(),
                {"status": "ready", "path": file_path},
            )


class WebServerRouter(APIRouter):
    def __init__(self, webserver: WebServer, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.webserver = webserver

        self.mapping: list[TRouteMap] = [
            {
                "path": "/",
                "callback": self.r_index,
                "methods": ["GET"],
            },
            {
                "path": "/api/convert",
                "callback": self.r_convert,
                "methods": ["POST"],
            },
            {
                "path": "/api/convert/status",
                "callback": self.r_convert_status,
                "methods": ["GET"],
            },
            {
                "path": "/api/convert/video",
                "callback": self.r_convert_video,
                "methods": ["GET"],
            },
        ]

        for route in self.mapping:
            self.add_api_route(
                route["path"], route["callback"], methods=route["methods"]
            )

    async def r_index(self) -> ORJSONResponse:
        return ORJSONResponse({"Hello": "World"}, status_code=status.HTTP_200_OK)

    async def r_convert(self, data: Mr_convert) -> ORJSONResponse:
        id = hashlib.md5(data.url.encode()).hexdigest()

        async with self.webserver.redis.locks["new_task"]:
            await self.webserver.redis.json.set(
                f"videos:{id}",
                RedisPath.root_path(),
                {"status": "started", "url": data.url},
                nx=True,
            )
            await self.webserver.redis.client.publish("new_task", id)

        return ORJSONResponse(
            {"status": "started", "id": id, "url": data.url},
            status_code=status.HTTP_202_ACCEPTED,
        )

    async def r_convert_status(self, data: Mr_convert_status) -> ORJSONResponse:
        async with self.webserver.redis.locks["videos_json"]:
            response: dict = await self.webserver.redis.json.get(f"videos:{data.id}")

        if not response:
            return ORJSONResponse(
                {"error": "No task or video found with the given id"},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        match response.get("status"):
            case "started":
                return ORJSONResponse(
                    {"status": "started"}, status_code=status.HTTP_200_OK
                )
            case "recording":
                return ORJSONResponse(
                    {"status": "recording"},
                    status_code=status.HTTP_200_OK,
                )
            case "processing":
                return ORJSONResponse(
                    {"status": "processing"}, status_code=status.HTTP_200_OK
                )
            case "ready":
                return ORJSONResponse(
                    {"status": "ready"}, status_code=status.HTTP_200_OK
                )
            case _:
                return ORJSONResponse(
                    {"error": "Something is wrong... Please try again later"},
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    async def r_convert_video(self, data: Mr_get_video) -> StreamingResponse:
        async with self.webserver.redis.locks["videos_json"]:
            response: dict = await self.webserver.redis.json.get(f"videos:{data.id}")

        if not response or response.get("status") != "ready":
            return ORJSONResponse(
                {
                    "error": "Video does not exist. Request for a video creation first or let the existing video finish"
                },
                status_code=status.HTTP_404_NOT_FOUND,
            )

        file_path: str = response.get("path")

        def iterfile():
            with open(file_path, "rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(), status_code=status.HTTP_200_OK, media_type="video/webm"
        )


class WebServer:
    def __init__(self, *, redis_url: str) -> None:
        self.app = FastAPI(lifespan=self.lifespan)

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=os.environ["CORS_ALLOW_ORIGINS"].split(","),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.router = WebServerRouter(self)
        self.app.include_router(self.router)

        self.redis = RedisHandler(self, redis_url)
        self.browser_cont = BrowserController(self)

        self.loop = asyncio.get_event_loop()

    @asynccontextmanager
    async def lifespan(self, _: FastAPI) -> TAsyncGenerator[None]:
        await self.redis.initialize()
        await self.browser_cont.initialize()

        yield

        await self.redis.close()
        await self.browser_cont.close()


def run():
    webserver = WebServer(redis_url=os.environ["REDIS_URL"])
    hconf = HypercornConfig()
    hconf.bind = "0.0.0.0:8000"

    asyncio.get_event_loop().run_until_complete(hypercorn_serve(webserver.app, hconf))
