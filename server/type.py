from __future__ import annotations
from typing import Any, Literal, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable as TCallable, Awaitable as TAwaitable

    from redis.asyncio.lock import Lock
    from fastapi.responses import Response


class TRouteMap(TypedDict):
    path: str
    callback: TCallable[[Any], TAwaitable[Response]]
    methods: list[Literal["GET", "POST", "PUT", "PATCH", "DELETE"]]


class TRedisLocks(TypedDict):
    new_task: Lock
    videos_json: Lock


class T_PubSubHandler_message(TypedDict):
    type: str
    pattern: bytes | None
    channel: bytes | None
    data: bytes
