"""MCP smoke test: connect to the RootCause MCP server like Claude Desktop does and call a few read tools.

Usage:
  uv run python scripts/mcp_smoke.py                    # streamable HTTP, http://localhost:8811/mcp
  uv run python scripts/mcp_smoke.py --stdio            # spawn `python -m rootcause.mcp_server` over stdio
Needs FalkorDB reachable (stdio mode uses FALKORDB_HOST/PORT, e.g. localhost / 6380).
"""

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client


async def exercise(session: ClientSession) -> None:
    await session.initialize()
    tools = await session.list_tools()
    print(f"{len(tools.tools)} tools:", ", ".join(sorted(t.name for t in tools.tools)))
    for name, args in [("who_owns", {"node_id": "payment"}), ("list_incidents", {"status": "all"}),
                       ("blast_radius", {"node_id": "payment"})]:
        res = await session.call_tool(name, args)
        text = res.content[0].text if res.content else ""
        print(f"\n> {name}({args})\n{json.dumps(json.loads(text), indent=1)[:700]}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8811/mcp")
    ap.add_argument("--stdio", action="store_true")
    args = ap.parse_args()
    if args.stdio:
        env = {**os.environ, "PYTHONPATH": "backend", "FALKORDB_HOST": os.environ.get("FALKORDB_HOST", "localhost"),
               "FALKORDB_PORT": os.environ.get("FALKORDB_PORT", "6380")}
        params = StdioServerParameters(command=sys.executable, args=["-m", "rootcause.mcp_server"], env=env)
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await exercise(s)
    else:
        async with streamablehttp_client(args.url) as (r, w, _), ClientSession(r, w) as s:
            await exercise(s)


if __name__ == "__main__":
    asyncio.run(main())
