"""RootCause MCP server (FastMCP). Exposes the investigation tools of rootcause/tools.py.

Transports:
- stdio: `python -m rootcause.mcp_server`            (Claude Desktop)
- streamable HTTP on :8811: `python -m rootcause.mcp_server --http`   (used by our LLM agent)
Read tools query FalkorDB directly; write tools are forwarded to the RootCause API (RC_API_URL) so all side
effects (and approval-token checks) happen in the API process.
"""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from rootcause.graph.client import get_graph
from rootcause.settings import get_settings
from rootcause.tools import ApiActions, Tools

INSTRUCTIONS = (
    "RootCause investigates incidents in the OpenTelemetry Demo shop using a FalkorDB graph of services, calls, "
    "queues, alerts, changes, journeys, teams and past incidents. Start with list_incidents, then "
    "rank_root_causes, trace_evidence_path, what_changed, measure_impact, find_similar_incidents, who_owns. "
    "Every result has an `evidence` list of graph node ids; cite them. Never execute an action without an "
    "approval token issued by a human in the RootCause UI."
)


def build(tools: Tools | None = None, host: str = "0.0.0.0", port: int = 8811) -> FastMCP:
    s = get_settings()
    t = tools or Tools(get_graph(), ApiActions(s.rc_api_url), s)
    mcp = FastMCP("rootcause", instructions=INSTRUCTIONS, host=host, port=port)

    @mcp.tool()
    async def list_incidents(status: str = "open") -> dict[str, Any]:
        """List incidents. status: 'open', 'resolved' or 'all'."""
        return await t.list_incidents(status)

    @mcp.tool()
    async def get_incident(incident_id: str) -> dict[str, Any]:
        """One incident: members, alerts, current root cause and confidence."""
        return await t.get_incident(incident_id)

    @mcp.tool()
    async def rank_root_causes(incident_id: str) -> dict[str, Any]:
        """Ranked root-cause hypotheses with their five signal scores (depth, self, pagerank, change, memory)."""
        return await t.rank_root_causes(incident_id)

    @mcp.tool()
    async def trace_evidence_path(from_id: str, to_id: str) -> dict[str, Any]:
        """Shortest BLAMES path between two anomalous nodes (e.g. frontend-proxy -> payment)."""
        return await t.trace_evidence_path(from_id, to_id)

    @mcp.tool()
    async def what_changed(node_id: str, window_min: float = 30) -> dict[str, Any]:
        """Flag changes and container restarts that hit a node in the last window_min minutes."""
        return await t.what_changed(node_id, window_min)

    @mcp.tool()
    async def measure_impact(incident_id: str) -> dict[str, Any]:
        """User journeys that require the failing services, with their drop in success rate."""
        return await t.measure_impact(incident_id)

    @mcp.tool()
    async def blast_radius(node_id: str) -> dict[str, Any]:
        """Everything upstream of a node (callers, transitively) and the journeys that need it."""
        return await t.blast_radius(node_id)

    @mcp.tool()
    async def predict_failure(node_id: str) -> dict[str, Any]:
        """What-if: services, queues and journeys predicted to break if this node fails."""
        return await t.predict_failure(node_id)

    @mcp.tool()
    async def find_similar_incidents(incident_id: str) -> dict[str, Any]:
        """Resolved past incidents with similar signals, how they were fixed, and whether one is a strong match."""
        return await t.find_similar_incidents(incident_id)

    @mcp.tool()
    async def who_owns(node_id: str) -> dict[str, Any]:
        """Owning team and who is on call."""
        return await t.who_owns(node_id)

    @mcp.tool()
    async def get_runbook(node_id: str) -> dict[str, Any]:
        """Runbooks for a service."""
        return await t.get_runbook(node_id)

    @mcp.tool()
    async def cypher_readonly(query: str) -> dict[str, Any]:
        """Run a read-only openCypher query on the FalkorDB graph (2 s timeout, max 200 rows)."""
        return await t.cypher_readonly(query)

    @mcp.tool()
    async def propose_action(incident_id: str) -> dict[str, Any]:
        """Draft remediation actions (flag revert / restart / page) with risk and side effects. Does not execute."""
        return await t.propose_action(incident_id)

    @mcp.tool()
    async def execute_action(action_id: str, approval_token: str) -> dict[str, Any]:
        """Execute an approved action. Needs the single-use approval token a human minted in the UI."""
        return await t.execute_action(action_id, approval_token)

    @mcp.tool()
    async def verify_recovery(incident_id: str) -> dict[str, Any]:
        """Check whether the incident's alerts have all resolved."""
        return await t.verify_recovery(incident_id)

    @mcp.tool()
    async def write_report(incident_id: str) -> dict[str, Any]:
        """Write the post-incident report (markdown) and store it in the graph."""
        return await t.write_report(incident_id)

    return mcp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true", help="streamable HTTP on --port instead of stdio")
    ap.add_argument("--port", type=int, default=8811)
    args = ap.parse_args()
    server = build(port=args.port)
    server.run(transport="streamable-http" if args.http else "stdio")


if __name__ == "__main__":
    main()
