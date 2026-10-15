"""Set a flagd flag's variant with an atomic JSON write (temp file + os.replace), the way the demo's flag UI does:
`defaultVariant`, or the on-branch of a `targeting.if: [cond, on, else]` rule when the flag has one.

No graph queries here: the flag watcher sees the file change and records the Change (actor='rootcause' because we
register it with `expect_change` first). The new JSON is validated before the file is replaced.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from rootcause.ingest.flag_watcher import effective_variant, expect_change


def with_variant(config: dict[str, Any], flag: str, variant: str) -> dict[str, Any]:
    """Pure: a copy of the flagd config with the flag switched to `variant`. Raises if flag/variant unknown."""
    flags = config.get("flags") or {}
    if flag not in flags:
        raise KeyError(f"unknown flag {flag}")
    variants = flags[flag].get("variants") or {}
    if variants and variant not in variants:
        raise KeyError(f"flag {flag} has no variant {variant!r} (has {sorted(variants)})")
    new = copy.deepcopy(config)
    spec = new["flags"][flag]
    branches = (spec.get("targeting") or {}).get("if")
    if isinstance(branches, list) and len(branches) == 3 and isinstance(branches[1], str):
        branches[1] = variant
    else:
        spec["defaultVariant"] = variant
    return new


def read_config(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def current_variant(path: str, flag: str) -> str | None:
    spec = (read_config(path).get("flags") or {}).get(flag)
    return effective_variant(spec) if spec else None


def set_variant(path: str, flag: str, variant: str, actor: str = "rootcause") -> dict[str, Any]:
    config = read_config(path)
    before = current_variant(path, flag)
    new = with_variant(config, flag, variant)
    text = json.dumps(new, indent=2)
    json.loads(text)  # validate before replacing the live file
    if actor == "rootcause":
        expect_change(flag, variant)
    target = Path(path)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".rootcause-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    os.replace(tmp, target)
    return {"flag": flag, "from": before, "to": variant}
