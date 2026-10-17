"""Fetch a GitHub repository for scanning: shallow `git clone` of a public https://github.com/<owner>/<repo> URL.

Nothing in the repository is executed: no hooks run on clone, symlinks are checked out as plain files, and the
scanner only reads text. Commit history (sha, time, subject; no author names) comes from `git log` per module.
No graph queries.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
MAX_REPO_MB = 600


def parse_url(url: str) -> tuple[str, str]:
    m = GITHUB.match(url.strip())
    if not m:
        raise ValueError("use a public GitHub URL like https://github.com/owner/repo")
    return m.group(1), m.group(2)


def _git(args: list[str], cwd: Path | None = None, timeout: int = 60) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                       check=False)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300] or f"git {args[0]} failed")
    return r.stdout


def _size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink()) / 1e6


def _rmtree(path: Path) -> None:
    """Delete a clone; git marks pack files read-only, which blocks deletion on Windows."""
    def unlock(func: Any, p: str, _exc: Any) -> None:
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=unlock)


def clone(url: str, base_dir: str) -> Path:
    owner, repo = parse_url(url)
    dest = Path(base_dir) / "repos" / f"{owner}__{repo}"
    if dest.exists():
        _rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", "--depth", "50", "--single-branch", "--no-tags", "-c", "core.symlinks=false",
          f"https://github.com/{owner}/{repo}.git", str(dest)], timeout=300)
    if _size_mb(dest) > MAX_REPO_MB:
        _rmtree(dest)
        raise ValueError(f"repository is larger than {MAX_REPO_MB} MB")
    return dest


def head(dest: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=dest).strip()


def module_commits(dest: Path, path: str, n: int = 3) -> list[dict[str, Any]]:
    out = _git(["log", f"-n{n}", "--format=%H%x09%at%x09%s", "--", path], cwd=dest)
    commits = []
    for line in out.splitlines():
        sha, ts, subject = (line.split("\t", 2) + ["", ""])[:3]
        if sha:
            commits.append({"sha": sha, "ts": int(ts) * 1000, "subject": subject[:200]})
    return commits
