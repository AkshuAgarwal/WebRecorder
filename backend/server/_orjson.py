from __future__ import annotations
from typing import Any

import orjson


class ORJSONDecoder:
    def decode(self, obj: bytes | bytearray | memoryview | str) -> Any:
        return orjson.loads(obj)


class ORJSONEncoder:
    def encode(self, obj: Any) -> str:
        return orjson.dumps(obj).decode("utf-8")
