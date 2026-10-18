"""The one place RootCause talks to an LLM: Google Gemini over its REST API (httpx, no SDK).

Used by the LLM agent (agent/loop.py, with function calling over our MCP tools), report narration, the
`llm_no_graph` chaos baseline and "Fix it in code". Key: GEMINI_API_KEY. Model: RC_LLM_MODEL
(default gemini-2.5-flash). Temperature 0 for repeatable answers. No graph queries here.
"""

from __future__ import annotations

from typing import Any

import httpx

from rootcause.settings import Settings

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# JSON-schema keys Gemini's function declarations accept (an OpenAPI subset); everything else is dropped
SCHEMA_KEYS = {"type", "description", "properties", "required", "items", "enum", "nullable", "format"}


def enabled(s: Settings) -> bool:
    return bool(s.gemini_api_key)


def gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Translate an MCP tool's JSON schema to the subset Gemini accepts (optional params: anyOf [X, null])."""
    if not isinstance(schema, dict):
        return {"type": "string"}
    if "anyOf" in schema:
        options = [o for o in schema["anyOf"] if o.get("type") != "null"]
        out = gemini_schema(options[0] if options else {"type": "string"})
        out["nullable"] = True
        if schema.get("description"):
            out["description"] = schema["description"]
        return out
    out = {k: v for k, v in schema.items() if k in SCHEMA_KEYS}
    if isinstance(out.get("type"), list):  # ["string", "null"]
        types = [t for t in out["type"] if t != "null"]
        out["type"] = types[0] if types else "string"
    if "properties" in out:
        out["properties"] = {k: gemini_schema(v) for k, v in out["properties"].items()}
        if not out["properties"]:
            del out["properties"]
    if "items" in out:
        out["items"] = gemini_schema(out["items"])
    out.setdefault("type", "object" if "properties" in out else "string")
    if isinstance(out.get("type"), str):
        out["type"] = out["type"].upper()
    return out


async def generate(s: Settings, contents: list[dict[str, Any]], system: str | None = None,
                   tools: list[dict[str, Any]] | None = None, timeout: float = 60) -> dict[str, Any]:
    """One generateContent call. Returns the first candidate's `content` ({role, parts})."""
    body: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": 0}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        body["tools"] = [{"functionDeclarations": tools}]
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(API.format(model=s.rc_llm_model), json=body,
                              headers={"x-goog-api-key": s.gemini_api_key})
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
    data = r.json()
    cands = data.get("candidates") or []
    if not cands or "content" not in cands[0]:
        reason = (cands[0].get("finishReason") if cands else None) or data.get("promptFeedback")
        raise RuntimeError(f"Gemini returned no answer ({reason})")
    return cands[0]["content"]


def text_of(content: dict[str, Any]) -> str:
    return "".join(p.get("text", "") for p in content.get("parts", []) if not p.get("thought"))


async def ask(s: Settings, prompt: str, system: str | None = None) -> str:
    """Single-turn text question."""
    content = await generate(s, [{"role": "user", "parts": [{"text": prompt}]}], system=system)
    return text_of(content).strip()
