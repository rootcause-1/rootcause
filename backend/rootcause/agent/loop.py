"""LLM agent: Claude picks RootCause tools over MCP (streamable HTTP, RC_MCP_URL) to investigate one incident.

Budget: 12 tool calls, 90 s. Every tool call is recorded as a (:Step) via agent/trail.py. The final answer is the
verdict JSON (same shape as autopilot). Write tools other than propose_action are not offered: the model can
draft actions but never execute them.

Model notes (Claude API): model from RC_LLM_MODEL (default claude-sonnet-5-5). That model rejects non-default
sampling parameters and forced tool_choice, so we send neither (the spec's "temperature 0" is not sendable);
output_config.effort is pinned instead for consistency. Server-side refusal fallbacks are enabled ("default").
The message history is append-only: assistant turns are appended as the full `response.content`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import anthropic
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from rootcause.agent.prompts import NARRATOR, SYSTEM
from rootcause.agent.trail import Trail
from rootcause.settings import Settings

log = logging.getLogger(__name__)
HIDDEN_TOOLS = {"execute_action", "verify_recovery", "write_report"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def parse_verdict(text: str) -> dict[str, Any] | None:
    """Pull the JSON object out of the model's final text."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _client(s: Settings) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None)


async def _create(client: anthropic.AsyncAnthropic, s: Settings, **kwargs: Any) -> Any:
    return await client.beta.messages.create(
        model=s.rc_llm_model, max_tokens=16000, betas=[FALLBACK_BETA], fallbacks="default",
        output_config={"effort": "medium"}, **kwargs)


async def investigate(s: Settings, trail: Trail, incident_id: str) -> dict[str, Any]:
    max_calls = int(s.c("agent", "max_tool_calls", default=12))
    budget = float(s.c("agent", "budget_seconds", default=90))
    client = _client(s)
    async with streamablehttp_client(s.rc_mcp_url) as (read, write, _), ClientSession(read, write) as mcp:
        await mcp.initialize()
        listed = await mcp.list_tools()
        tools = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
                 for t in listed.tools if t.name not in HIDDEN_TOOLS]
        messages: list[dict[str, Any]] = [{"role": "user", "content":
                                           f"Investigate incident {incident_id}. Finish with the verdict JSON."}]
        calls = 0
        deadline = asyncio.get_running_loop().time() + budget
        while True:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("agent budget exhausted")
            resp = await _create(client, s, system=SYSTEM, tools=tools, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "refusal":
                raise RuntimeError("model declined the request")
            if resp.stop_reason != "tool_use":
                text = "".join(b.text for b in resp.content if b.type == "text")
                verdict = parse_verdict(text)
                if verdict is None:
                    raise ValueError("agent did not return verdict JSON")
                return verdict
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                calls += 1
                if calls > max_calls:
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                    "content": "tool budget exhausted: answer now with the verdict JSON"})
                    continue
                out = await mcp.call_tool(block.name, block.input)
                text = "".join(getattr(c, "text", "") for c in out.content)
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {"text": text}
                if isinstance(data, dict):
                    await trail.record(block.name, dict(block.input), data)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": text,
                                "is_error": bool(out.isError)})
            messages.append({"role": "user", "content": results})


def narrator(s: Settings):
    """Report narration callable for actions/report.py (None if no API key)."""
    if not s.anthropic_api_key:
        return None
    client = _client(s)

    async def narrate(inc: dict[str, Any], path: list[str], similar: list[dict[str, Any]]) -> str:
        facts = {k: inc.get(k) for k in ("id", "root_target", "confidence", "ttr_ms", "resolution")}
        facts.update(path=path, changes=inc["changes"], impact=inc["impact"],
                     actions=[{k: a.get(k) for k in ("kind", "target", "status")} for a in inc["actions"]],
                     similar=[{"incident": x["incident"], "score": x["score"]} for x in similar])
        resp = await _create(client, s, system=NARRATOR,
                             messages=[{"role": "user", "content": json.dumps(facts, default=str)}])
        if resp.stop_reason == "refusal":
            raise RuntimeError("narration declined")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    return narrate
