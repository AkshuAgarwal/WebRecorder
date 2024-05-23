FROM python:3.11-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
COPY ./server /code/server

RUN apt update && apt upgrade -y
RUN apt install -y --no-install-recommends ffmpeg

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
RUN playwright install chromium
RUN playwright install-deps
