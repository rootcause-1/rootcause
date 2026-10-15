"""Small shared helpers: ids, time, JSON. No graph queries."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def loads(text: Any, default: Any = None) -> Any:
    if not isinstance(text, str):
        return text if text is not None else default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def clean(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Drop the all-null maps that OPTIONAL MATCH + collect({...}) produces when nothing matched."""
    return [x for x in items or [] if x and x.get(key) is not None]
