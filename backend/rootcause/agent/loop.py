"""LLM agent: Gemini picks RootCause tools over MCP (streamable HTTP, RC_MCP_URL) to investigate one incident.

Budget: 12 tool calls, 90 s. Every tool call is recorded as a (:Step) via agent/trail.py. The final answer is the
verdict JSON (same shape as autopilot). Write tools other than propose_action are not offered: the model can
draft actions but never execute them.

Model notes (Gemini API, rootcause/llm.py): model from RC_LLM_MODEL (default gemini-2.5-flash), temperature 0.
MCP tool schemas are translated to Gemini function declarations; the model's turns are appended unchanged
(they may carry thought signatures), tool results go back as functionResponse parts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from rootcause import llm
from rootcause.agent.prompts import NARRATOR, SYSTEM
from rootcause.agent.trail import Trail
from rootcause.settings import Settings

log = logging.getLogger(__name__)
HIDDEN_TOOLS = {"execute_action", "verify_recovery", "write_report"}


def parse_verdict(text: str) -> dict[str, Any] | None:
    """Pull the JSON object out of the model's final text."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def investigate(s: Settings, trail: Trail, incident_id: str) -> dict[str, Any]:
    max_calls = int(s.c("agent", "max_tool_calls", default=12))
    budget = float(s.c("agent", "budget_seconds", default=90))
    async with streamablehttp_client(s.rc_mcp_url) as (read, write, _), ClientSession(read, write) as mcp:
        await mcp.initialize()
        listed = await mcp.list_tools()
        tools = [{"name": t.name, "description": t.description or "", "parameters": llm.gemini_schema(t.inputSchema)}
                 for t in listed.tools if t.name not in HIDDEN_TOOLS]
        contents: list[dict[str, Any]] = [{"role": "user", "parts": [
            {"text": f"Investigate incident {incident_id}. Finish with the verdict JSON."}]}]
        calls = 0
        deadline = asyncio.get_running_loop().time() + budget
        while True:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("agent budget exhausted")
            content = await llm.generate(s, contents, system=SYSTEM, tools=tools)
            contents.append({"role": "model", "parts": content.get("parts", [])})
            fcalls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
            if not fcalls:
                verdict = parse_verdict(llm.text_of(content))
                if verdict is None:
                    raise ValueError("agent did not return verdict JSON")
                return verdict
            results = []
            for fc in fcalls:
                name, args = fc["name"], dict(fc.get("args") or {})
                calls += 1
                if calls > max_calls:
                    results.append({"functionResponse": {"name": name, "response": {
                        "error": "tool budget exhausted: answer now with the verdict JSON"}}})
                    continue
                out = await mcp.call_tool(name, args)
                text = "".join(getattr(c, "text", "") for c in out.content)
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {"text": text}
                if isinstance(data, dict):
                    await trail.record(name, args, data)
                response = data if isinstance(data, dict) else {"result": data}
                if out.isError:
                    response = {"error": text}
                results.append({"functionResponse": {"name": name, "response": response}})
            contents.append({"role": "user", "parts": results})


def narrator(s: Settings):
    """Report narration callable for actions/report.py (None if no Gemini key)."""
    if not llm.enabled(s):
        return None

    async def narrate(inc: dict[str, Any], path: list[str], similar: list[dict[str, Any]]) -> str:
        facts = {k: inc.get(k) for k in ("id", "root_target", "confidence", "ttr_ms", "resolution")}
        facts.update(path=path, changes=inc["changes"], impact=inc["impact"],
                     actions=[{k: a.get(k) for k in ("kind", "target", "status")} for a in inc["actions"]],
                     similar=[{"incident": x["incident"], "score": x["score"]} for x in similar])
        return await llm.ask(s, json.dumps(facts, default=str), system=NARRATOR)

    return narrate
