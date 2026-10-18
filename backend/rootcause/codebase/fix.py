"""Fix it in code: Gemini writes a fix for the incident's root cause and RootCause opens it as a GitHub pull request.

1. Pick the files: where the root-cause module reads the flag that changed before the incident (READ_IN edges,
   from code_for_node); otherwise the module's first flag read.
2. Fetch those files from the fork on GitHub, give Gemini the incident facts + the files (prompts.FIXER).
3. Apply Gemini's find/replace edits only if every `find` matches exactly once (`apply_edits`, pure, tested).
4. Open a pull request on `code.pr_repo` from branch rootcause/<incident>; record (:PullRequest)-[:FIXES]->(:Incident)
   and -[:CHANGES]->(:CodeModule).
Nothing is merged or deployed: a person reviews the PR. RootCause does not run the changed code; the fork's CI does.
Queries: code_for_node (codebase/store.py), create_pull_request.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from rootcause.codebase import store
from rootcause.codebase.github import GitHub
from rootcause.graph.client import GraphDB
from rootcause.settings import Settings
from rootcause.util import now_ms

MAX_FILE_CHARS = 40_000
Writer = Callable[[str, str], Awaitable[str]]  # (system prompt, user message) -> model text


def pr_repo(s: Settings) -> str | None:
    """owner/repo of our fork: env RC_PR_REPO, else code.pr_repo in rootcause.yaml."""
    return os.environ.get("RC_PR_REPO") or s.c("code", "pr_repo")


def enabled(s: Settings) -> str | None:
    """None when fix PRs can be opened, else the reason they can't (shown in the UI)."""
    if not s.gemini_api_key:
        return "needs GEMINI_API_KEY (Gemini writes the fix)"
    if not s.github_token:
        return "needs GITHUB_TOKEN (to open the pull request)"
    if not pr_repo(s):
        return "needs code.pr_repo (your fork, owner/repo)"
    return None


def pick_files(code: dict[str, Any], changed_flags: list[str], limit: int = 2) -> list[str]:
    reads = code.get("reads") or []
    hit = [r["file"] for r in reads if r["flag"] in changed_flags]
    files = list(dict.fromkeys(hit or [r["file"] for r in reads[:1]]))
    return files[:limit]


def apply_edits(files: dict[str, str], edits: list[dict[str, Any]]) -> dict[str, str]:
    """Apply exact find/replace edits; every `find` must occur exactly once in its file. Returns changed files."""
    out = dict(files)
    for e in edits:
        path, find, repl = e.get("file"), e.get("find") or "", e.get("replace")
        if path not in out:
            raise ValueError(f"edit for a file that was not given: {path}")
        if not find or repl is None:
            raise ValueError("an edit needs `find` and `replace`")
        n = out[path].count(find)
        if n != 1:
            raise ValueError(f"`find` matches {n} times in {path}; it must match exactly once")
        out[path] = out[path].replace(find, repl, 1)
    changed = {p: t for p, t in out.items() if t != files[p]}
    if not changed:
        raise ValueError("the proposed edits change nothing")
    return changed


def facts_for(inc: dict[str, Any], code: dict[str, Any]) -> dict[str, Any]:
    top = (inc.get("hypotheses") or [{}])[0]
    return {"incident": inc["id"], "root_cause": inc.get("root_target"), "confidence": inc.get("confidence"),
            "signals": {k: top.get(k) for k in ("depth", "self", "pagerank", "change", "memory")},
            "changes": [{k: c.get(k) for k in ("kind", "target", "from_variant", "to")} for c in inc.get("changes", [])],
            "alerts": sorted({f"{a['target']}:{a['kind']}" for a in inc.get("alerts", [])}),
            "impact": inc.get("impact", []), "module": code.get("path"), "language": code.get("language"),
            "flag_reads": code.get("reads")}


def pr_body(inc: dict[str, Any], code: dict[str, Any], plan: dict[str, Any], files: list[str]) -> str:
    changes = ", ".join(f"`{c['target']}` {c.get('from_variant')} → {c.get('to')}" for c in inc.get("changes", [])
                        if c.get("kind") == "flag") or "none found"
    impact = ", ".join(f"{i['journey']} −{i['pct']:.0%}" for i in inc.get("impact", [])) or "none measured"
    path = " → ".join(inc.get("evidence_path") or []) or inc.get("root_target")
    return "\n".join([
        f"**Opened by RootCause for incident {inc['id']}.** Please review before merging.", "",
        f"{plan.get('explanation', '').strip()}", "",
        "### What RootCause found",
        f"- Root cause: `{inc.get('root_target')}` (confidence {float(inc.get('confidence') or 0):.2f})",
        f"- Evidence path (BLAMES chain in the FalkorDB graph): {path}",
        f"- Change just before the alerts: {changes}",
        f"- Customer impact: {impact}",
        f"- Code: {', '.join(f'`{f}`' for f in files)} ({code.get('language')})", "",
        "### Not done by RootCause",
        "- The changed code was not run or tested by RootCause; your CI checks it.",
        "- Nothing is merged or deployed until a person approves this pull request.",
        "", "_Change written by Gemini from the incident facts above._",
    ])


async def open_fix_pr(db: GraphDB, s: Settings, inc: dict[str, Any], write: Writer,
                      gh: GitHub | None = None) -> dict[str, Any]:
    from rootcause.agent.loop import parse_verdict
    from rootcause.agent.prompts import FIXER

    root = inc.get("root_target") or ""
    code = await store.for_node(db, root)
    if not code:
        raise ValueError(f"no scanned code implements {root}")
    flags = [c["target"] for c in inc.get("changes", []) if c.get("kind") == "flag"]
    paths = pick_files(code, flags)
    if not paths:
        raise ValueError(f"no flag read located in {code.get('path')}")
    gh = gh or GitHub(s.github_token, pr_repo(s))
    base = await gh.default_branch()
    files: dict[str, str] = {}
    for p in paths:
        text, _ = await gh.get_file(p, base)
        if len(text) > MAX_FILE_CHARS:
            raise ValueError(f"{p} is too large for an automatic fix")
        files[p] = text

    user = json.dumps(facts_for(inc, code), default=str) + "\n\n" + "\n\n".join(
        f"=== {p} ===\n{t}" for p, t in files.items())
    plan = parse_verdict(await write(FIXER, user)) or {}
    changed = apply_edits(files, plan.get("edits") or [])
    title = (plan.get("title") or f"Fix {root} failure from incident {inc['id']}")[:90]
    branch = f"rootcause/{inc['id'].lower()}-{now_ms() // 1000}"
    pr = await gh.open_pr(changed, branch, title, pr_body(inc, code, plan, list(changed)),
                          message=f"{title}\n\nOpened by RootCause for {inc['id']}.")
    await db.run("create_pull_request", url=pr["url"], number=pr["number"], branch=branch, title=title,
                 incident=inc["id"], module=code["id"], now=now_ms())
    return pr | {"title": title, "explanation": plan.get("explanation", ""), "files": list(changed)}
