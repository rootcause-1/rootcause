"""Minimal GitHub REST client for the "fix it in code" action: read a file, create a branch, commit files, open a PR.

Only ever talks to the one repository configured as `code.pr_repo` (our own fork), with the token in GITHUB_TOKEN.
It never merges anything: a person reviews and merges the pull request. No graph queries.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str, repo: str, client: httpx.AsyncClient | None = None):
        if not token:
            raise GitHubError("GITHUB_TOKEN is not set")
        if repo.count("/") != 1:
            raise GitHubError("code.pr_repo must look like owner/repo")
        self.repo = repo
        self.client = client or httpx.AsyncClient(timeout=30)
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}

    async def _req(self, method: str, path: str, **kw: Any) -> Any:
        r = await self.client.request(method, f"{API}/repos/{self.repo}{path}", headers=self.headers, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json().get("message", r.text)
            except ValueError:
                msg = r.text
            raise GitHubError(f"GitHub {method} {path}: {r.status_code} {msg}"[:300])
        return r.json() if r.content else {}

    async def default_branch(self) -> str:
        return (await self._req("GET", ""))["default_branch"]

    async def get_file(self, path: str, ref: str) -> tuple[str, str]:
        """(text, blob sha) of a file at a ref."""
        d = await self._req("GET", f"/contents/{path}", params={"ref": ref})
        return base64.b64decode(d["content"]).decode("utf-8"), d["sha"]

    async def open_pr(self, files: dict[str, str], branch: str, title: str, body: str,
                      message: str) -> dict[str, Any]:
        base = await self.default_branch()
        head_sha = (await self._req("GET", f"/git/ref/heads/{base}"))["object"]["sha"]
        await self._req("POST", "/git/refs", json={"ref": f"refs/heads/{branch}", "sha": head_sha})
        for path, text in files.items():
            _, blob = await self.get_file(path, branch)
            await self._req("PUT", f"/contents/{path}", json={
                "message": message, "branch": branch, "sha": blob,
                "content": base64.b64encode(text.encode("utf-8")).decode("ascii")})
        pr = await self._req("POST", "/pulls", json={"title": title, "head": branch, "base": base, "body": body})
        return {"url": pr["html_url"], "number": pr["number"], "branch": branch, "base": base}
