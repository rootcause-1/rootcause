"""Fix it in code: pure helpers and the GitHub client against a fake GitHub (httpx MockTransport, no network)."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from rootcause.codebase import fix
from rootcause.codebase.github import GitHub, GitHubError

FILE = "function charge(req) {\n  if (flags.paymentFailure) {\n    throw new Error('boom');\n  }\n  return ok();\n}\n"


def test_apply_edits_needs_exactly_one_match():
    files = {"src/payment/charge.js": FILE}
    out = fix.apply_edits(files, [{"file": "src/payment/charge.js", "find": "    throw new Error('boom');\n",
                                   "replace": "    return retryLater();\n"}])
    assert "retryLater" in out["src/payment/charge.js"] and "boom" not in out["src/payment/charge.js"]
    for bad in ([{"file": "src/payment/charge.js", "find": "  ", "replace": "x"}],          # matches many times
                [{"file": "other.js", "find": "a", "replace": "b"}],                      # file not given
                [{"file": "src/payment/charge.js", "find": "nope", "replace": "x"}],      # no match
                [{"file": "src/payment/charge.js", "find": "ok();", "replace": "ok();"}]):  # no change
        with pytest.raises(ValueError):
            fix.apply_edits(files, bad)


def test_pick_files_prefers_the_flag_that_changed():
    code = {"reads": [{"flag": "a", "file": "x.js", "line": 1}, {"flag": "paymentFailure", "file": "y.js", "line": 9}]}
    assert fix.pick_files(code, ["paymentFailure"]) == ["y.js"]
    assert fix.pick_files(code, ["other"]) == ["x.js"]
    assert fix.pick_files({"reads": []}, ["a"]) == []


def test_enabled_lists_what_is_missing():
    class S:
        anthropic_api_key, github_token = "", ""

        def c(self, *a, **k):
            return None

    s = S()
    assert "ANTHROPIC_API_KEY" in fix.enabled(s)
    s.anthropic_api_key = "k"
    assert "GITHUB_TOKEN" in fix.enabled(s)
    s.github_token = "t"
    assert "pr_repo" in fix.enabled(s)
    s.c = lambda *a, **k: "acme/shop"
    assert fix.enabled(s) is None


def test_pr_body_states_what_was_not_done():
    inc = {"id": "INC-0001", "root_target": "payment", "confidence": 0.9, "evidence_path": ["checkout", "payment"],
           "changes": [{"kind": "flag", "target": "paymentFailure", "from_variant": "off", "to": "100%"}],
           "impact": [{"journey": "journey:checkout", "pct": 0.7}]}
    body = fix.pr_body(inc, {"language": "JavaScript"}, {"explanation": "Guard the flag."}, ["src/payment/charge.js"])
    assert "INC-0001" in body and "checkout → payment" in body and "paymentFailure" in body
    assert "not run or tested by RootCause" in body and "Nothing is merged" in body


class FakeGitHub:
    """Just enough of the GitHub REST API for open_pr."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.files = {"src/payment/charge.js": FILE}
        self.pushed: dict[str, str] = {}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path.removeprefix("/repos/acme/shop")
        self.calls.append((req.method, path))
        assert req.headers["authorization"] == "Bearer t"
        if req.method == "GET" and path == "":
            return httpx.Response(200, json={"default_branch": "main"})
        if req.method == "GET" and path == "/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": "base123"}})
        if req.method == "POST" and path == "/git/refs":
            return httpx.Response(201, json={"ref": json.loads(req.content)["ref"]})
        if req.method == "GET" and path.startswith("/contents/"):
            text = self.files[path.removeprefix("/contents/")]
            return httpx.Response(200, json={"content": base64.b64encode(text.encode()).decode(), "sha": "blob1"})
        if req.method == "PUT" and path.startswith("/contents/"):
            body = json.loads(req.content)
            assert body["sha"] == "blob1" and body["branch"].startswith("rootcause/")
            self.pushed[path.removeprefix("/contents/")] = base64.b64decode(body["content"]).decode()
            return httpx.Response(200, json={})
        if req.method == "POST" and path == "/pulls":
            assert json.loads(req.content)["base"] == "main"
            return httpx.Response(201, json={"html_url": "https://github.com/acme/shop/pull/7", "number": 7})
        return httpx.Response(404, json={"message": "Not Found"})


def fake_gh(fake: FakeGitHub) -> GitHub:
    return GitHub("t", "acme/shop", client=httpx.AsyncClient(transport=httpx.MockTransport(fake)))


async def test_github_client_opens_a_pull_request():
    fake = FakeGitHub()
    pr = await fake_gh(fake).open_pr({"src/payment/charge.js": "new"}, "rootcause/inc-0001-1", "Fix", "body", "msg")
    assert pr == {"url": "https://github.com/acme/shop/pull/7", "number": 7, "branch": "rootcause/inc-0001-1",
                  "base": "main"}
    assert fake.pushed == {"src/payment/charge.js": "new"}
    assert ("POST", "/git/refs") in fake.calls and fake.calls[-1] == ("POST", "/pulls")


async def test_github_errors_are_readable():
    gh = GitHub("t", "acme/shop", client=httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(403, json={"message": "Resource not accessible by integration"}))))
    with pytest.raises(GitHubError, match="403 Resource not accessible"):
        await gh.default_branch()
    with pytest.raises(GitHubError):
        GitHub("", "acme/shop")
