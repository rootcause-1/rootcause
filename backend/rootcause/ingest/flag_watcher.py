"""flagd config watcher: polls the flagd JSON every 2 s and emits a `flag_config` input when it changes.

The pipeline diffs consecutive configs (`diff_flags`) and writes one `(:Change {kind:'flag'})` per changed
`defaultVariant` with the `create_flag_change` query. The actor is 'rootcause' when RootCause itself made the
change (actions/flagd.py registers it with `expect_change`), otherwise 'unknown'.

The engine may use the existence and timing of a Change. It never reads which flag means which root cause.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_expected: dict[tuple[str, str], float] = {}


def expect_change(flag: str, variant: str, ttl_s: float = 60.0) -> None:
    """Called by actions/flagd.py right before it writes, so the resulting Change gets actor='rootcause'."""
    _expected[(flag, variant)] = time.time() + ttl_s


def actor_for(flag: str, variant: str) -> str:
    deadline = _expected.pop((flag, variant), None)
    return "rootcause" if deadline and deadline >= time.time() else "unknown"


def effective_variant(spec: dict[str, Any]) -> str:
    """The variant a flag is switched to, as the demo's flag UI sets it: a flag with a targeting rule of the form
    `if: [condition, <on-branch>, <else>]` (e.g. productCatalogFailure for one product id) is switched through the
    on-branch; every other flag through `defaultVariant`."""
    branches = (spec.get("targeting") or {}).get("if")
    if isinstance(branches, list) and len(branches) == 3 and isinstance(branches[1], str):
        return branches[1]
    return str(spec.get("defaultVariant"))


def default_variants(config: dict[str, Any]) -> dict[str, str]:
    return {name: effective_variant(spec) for name, spec in (config.get("flags") or {}).items()}


def diff_flags(old: dict[str, str] | None, new: dict[str, str]) -> list[tuple[str, str | None, str]]:
    """[(flag, from, to)] for every flag whose defaultVariant changed. First observation yields nothing."""
    if old is None:
        return []
    return [(f, old.get(f), v) for f, v in sorted(new.items()) if old.get(f) != v]


class FlagWatcher:
    def __init__(self, path: str, poll_s: float, emit: Callable[[dict[str, Any]], Awaitable[None]]):
        self.path = Path(path)
        self.poll_s = poll_s
        self.emit = emit
        self._last_text: str | None = None

    async def run(self) -> None:
        if not self.path.exists():
            log.warning("flagd config not found at %s (VERIFY FLAGD_CONFIG_PATH); flag watcher idle", self.path)
        while True:
            try:
                text = self.path.read_text(encoding="utf-8")
                if text != self._last_text:
                    self._last_text = text
                    await self.emit({"type": "flag_config", "ts": int(time.time() * 1000), "data": json.loads(text)})
            except FileNotFoundError:
                pass
            except json.JSONDecodeError:
                log.debug("flagd config mid-write; retry next poll")
            except Exception as exc:
                log.warning("flag watcher: %s", exc)
            await asyncio.sleep(self.poll_s)
