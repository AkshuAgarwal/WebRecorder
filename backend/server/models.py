from __future__ import annotations

from pydantic import BaseModel


class Mr_convert(BaseModel):
    url: str


class Mr_convert_status(BaseModel):
    id: str


class Mr_get_video(BaseModel):
    id: str
