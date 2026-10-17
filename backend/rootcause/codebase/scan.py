"""Codebase scanner: reads a checked-out repository (never runs any of it) and describes it as plain data.

- modules: one per compose service and per folder under src/, services/, apps/, cmd/, packages/ (language, files,
  lines of code, CODEOWNERS owners), named after the service it implements;
- declares: dependencies the repo declares (compose `depends_on`, and `<NAME>_ADDR/_HOST/_URL` env vars naming
  another service);
- rpc: gRPC services and their methods from .proto files, matched to the module that implements them;
- flag_reads: where in the code each known feature flag key is read (file and line).

Pure: no graph access. codebase/graph.py writes the result with the code_* queries. Explanation only: nothing here
feeds the root-cause ranking.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

import yaml

SRC_ROOTS = ("src", "services", "apps", "cmd", "packages")
LANG = {".py": "Python", ".go": "Go", ".js": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript",
        ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".rb": "Ruby", ".php": "PHP",
        ".rs": "Rust", ".cpp": "C++", ".cc": "C++", ".h": "C++", ".ex": "Elixir", ".exs": "Elixir",
        ".scala": "Scala", ".swift": "Swift", ".dart": "Dart"}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target", "__pycache__", ".venv", "obj", "bin",
             ".next", "coverage", "genproto", "cypress"}
DEP_ENV = re.compile(r"^([A-Z][A-Z0-9_]*?)_(ADDR|HOST|URL|ENDPOINT)$")
MAX_FILE_BYTES = 400_000


def kebab(name: str) -> str:
    """PaymentService -> payment, ProductCatalogService -> product-catalog, PRODUCT_CATALOG -> product-catalog."""
    name = re.sub(r"Service$", "", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name)
    return name.replace("_", "-").lower()


def _walk_code(root: Path):
    """Code files under root (no symlinks followed, generated/vendor folders skipped)."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            p = Path(dirpath) / f
            if p.suffix in LANG and not p.is_symlink():
                yield p


def is_test(p: Path) -> bool:
    parts = {x.lower() for x in p.parts}
    name = p.stem.lower()
    return bool(parts & {"test", "tests", "__tests__", "spec", "e2e"}) or name.endswith(("_test", "tests", ".test",
                                                                                         ".spec", "test"))


def _generated(path: str) -> bool:
    return bool(re.search(r"(_gen|\.gen|\.pb|_pb2|generated)", path, re.I))


def _read(p: Path) -> str:
    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def compose_services(root: Path) -> dict[str, dict[str, Any]]:
    """Services from every compose file at the repo root: build dir guess, depends_on, env var names."""
    out: dict[str, dict[str, Any]] = {}
    files = sorted({*root.glob("compose*.y*ml"), *root.glob("docker-compose*.y*ml")})
    for f in files:
        try:
            doc = yaml.safe_load(_read(f)) or {}
        except yaml.YAMLError:
            continue
        for name, s in (doc.get("services") or {}).items():
            s = s or {}
            entry = out.setdefault(name, {"build": None, "depends_on": set(), "env": set()})
            build = s.get("build")
            if build:
                entry["build"] = build if isinstance(build, str) else (build.get("dockerfile") or build.get("context"))
            deps = s.get("depends_on") or []
            entry["depends_on"] |= set(deps.keys() if isinstance(deps, dict) else deps)
            env = s.get("environment") or []
            names = env.keys() if isinstance(env, dict) else [str(e).split("=", 1)[0] for e in env]
            entry["env"] |= {str(n).strip() for n in names}
    return out


def _exact_dir(root: Path, name: str) -> str | None:
    for base in SRC_ROOTS:
        if (root / base / name).is_dir():
            return f"{base}/{name}"
    return None


def _build_dir(root: Path, build: Any) -> str | None:
    if isinstance(build, str) and "$" not in build:
        p = (root / build)
        p = p if p.is_dir() else p.parent
        rel = p.resolve().relative_to(root.resolve()).as_posix() if p.exists() else None
        return rel if rel and rel != "." else None
    return None


def codeowners(root: Path) -> list[tuple[str, list[str]]]:
    for p in (root / ".github" / "CODEOWNERS", root / "CODEOWNERS", root / "docs" / "CODEOWNERS"):
        if p.exists():
            rules = []
            for line in _read(p).splitlines():
                parts = line.split("#", 1)[0].split()
                if len(parts) >= 2:
                    rules.append((parts[0], parts[1:]))
            return rules
    return []


def owners_for(path: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    """Last matching CODEOWNERS rule wins (simplified: '*', globs and folder prefixes)."""
    found: list[str] = []
    for pattern, owners in rules:
        pat = pattern.strip("/")
        if pattern == "*" or path == pat or path.startswith(pat + "/") or fnmatch.fnmatch(path, pat):
            found = owners
    return found


def proto_services(root: Path) -> list[dict[str, Any]]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            if not f.endswith(".proto"):
                continue
            p = Path(dirpath) / f
            current: dict[str, Any] | None = None
            for line in _read(p).splitlines():
                m = re.match(r"\s*service\s+(\w+)\s*\{", line)
                if m:
                    current = {"name": m.group(1), "methods": [], "file": p.relative_to(root).as_posix()}
                    out.append(current)
                    continue
                m = re.match(r"\s*rpc\s+(\w+)\s*\(", line)
                if m and current is not None:
                    current["methods"].append(m.group(1))
                if current is not None and re.match(r"^\}", line):
                    current = None
    return out


def scan(root: Path, flags: list[str] | None = None) -> dict[str, Any]:
    root = Path(root)
    comp = compose_services(root)
    rules = codeowners(root)
    modules: dict[str, dict[str, Any]] = {}
    for name in comp:  # a folder named like the service wins, then the build path if no one claimed it
        modules[name] = {"name": name, "path": _exact_dir(root, name)}
    claimed = {m["path"] for m in modules.values() if m["path"]}
    for name, s in comp.items():
        guess = None if modules[name]["path"] else _build_dir(root, s["build"])
        if guess and not any(guess == c or guess.startswith(c + "/") for c in claimed):
            modules[name]["path"] = guess
            claimed.add(guess)
    for base in SRC_ROOTS:
        if (root / base).is_dir():
            for d in sorted((root / base).iterdir()):
                if d.is_dir() and not d.name.startswith(".") and d.name not in modules:
                    modules[d.name] = {"name": d.name, "path": f"{base}/{d.name}"}

    flag_reads: list[dict[str, Any]] = []
    patterns = {f: re.compile(rf"\b{re.escape(f)}\b") for f in (flags or [])}
    for m in modules.values():
        langs: dict[str, int] = {}
        files = loc = 0
        if m["path"]:
            for p in _walk_code(root / m["path"]):
                text = _read(p)
                files += 1
                loc += text.count("\n")
                langs[LANG[p.suffix]] = langs.get(LANG[p.suffix], 0) + 1
                for flag, rx in (patterns.items() if not is_test(p) else ()):
                    for i, line in enumerate(text.splitlines(), start=1):
                        if rx.search(line):
                            flag_reads.append({"flag": flag, "module": m["name"],
                                               "file": p.relative_to(root).as_posix(), "line": i})
                            break
        m.update(language=max(langs, key=langs.get) if langs else None, files=files, loc=loc,
                 owners=owners_for(m["path"], rules) if m["path"] else [], kind="code" if files else "image")

    # up to 3 reads per (flag, module), hand-written files before generated ones
    flag_reads.sort(key=lambda r: (r["flag"], r["module"], _generated(r["file"]), r["file"]))
    kept: dict[tuple[str, str], int] = {}
    reads = []
    for r in flag_reads:
        k = (r["flag"], r["module"])
        if kept.get(k, 0) < 3:
            kept[k] = kept.get(k, 0) + 1
            reads.append(r)

    declares: list[dict[str, Any]] = []
    for name, s in comp.items():
        for dep in sorted(s["depends_on"]):
            if dep in modules and dep != name:
                declares.append({"src": name, "dst": dep, "via": "depends_on"})
        for env in sorted(s["env"]):
            m = DEP_ENV.match(env)
            dep = kebab(m.group(1)) if m else None
            if dep and dep in modules and dep != name and not any(
                    d["src"] == name and d["dst"] == dep for d in declares):
                declares.append({"src": name, "dst": dep, "via": env})

    rpc = []
    for r in proto_services(root):
        mod = kebab(r["name"])
        rpc.append({"id": f"rpc:{r['name']}", "name": r["name"], "methods": r["methods"], "file": r["file"],
                    "module": mod if mod in modules else None})
    return {"modules": sorted(modules.values(), key=lambda x: x["name"]), "declares": declares, "rpc": rpc,
            "flag_reads": reads}
