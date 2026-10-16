// The company map: the shop's customers on the left, the services grouped by the team that owns them (with who is on
// call), shared infrastructure at the bottom. Requests flow left -> right; one broken box visibly ripples out to the
// teams and the customers who depend on it.
//
// Everything is the graph in FalkorDB, refreshed every 5 s (GET /api/graph: graph_nodes, graph_edges, graph_journeys,
// graph_teams):
// - customer cards = Journey nodes (requests per hour, how many are failing); a journey turns red when a service it
//   critically REQUIRES is alerting or its success rate drops;
// - service cards = Service / Queue / Datastore nodes, in the lane of the Team that OWNS them;
// - dots travel along each CALLS / USES / messaging edge at its request rate; red dots = its share of failing requests;
// - amber = alerting (:Anomalous), red = root cause, animated dashed line = evidence path; rings: blue = touched by the
//   fix, purple = predicted to fail, white = cited by the agent step you are hovering.
import { useMemo } from "react";
import type { Graph, GraphEdge, GraphNode, Journey, Team } from "../api";
import { C, errColour } from "../palette";

export type Overlay = { root?: string | null; path?: string[]; cited?: string[]; predicted?: string[]; blast?: string[] };

const FLOW = new Set(["CALLS", "USES", "PRODUCES_TO", "CONSUMED_BY"]);
const HIDDEN = new Set(["flagd", "flagd-ui", "otel-collector", "load-generator", "frontend-web"]);
/** What each service is for, in business terms (the technical id is shown under it). */
export const BUSINESS: Record<string, string> = {
  "frontend-proxy": "Website gateway", frontend: "Web storefront", "image-provider": "Product images",
  cart: "Shopping cart", ad: "Ads", recommendation: "Recommendations", "product-reviews": "Product reviews",
  checkout: "Checkout", payment: "Payments", currency: "Currency exchange", "fraud-detection": "Fraud detection",
  accounting: "Accounting", shipping: "Shipping", quote: "Shipping quotes", email: "Order emails", kafka: "Event bus",
  "product-catalog": "Product catalog", agent: "AI shopping assistant", "queue:orders": "Orders queue",
  "db:astronomy-db": "Product database", "cache:valkey-cart": "Cart store",
};
export const nameOf = (id: string) => BUSINESS[id] ?? id.replace(/^(queue|db|cache):/, "");

const W = 146, H = 50, COL = 168, ROW = 60, PAD = 18, JW = 168, JH = 54, GAP = 76, BAND_HEAD = 26, BAND_GAP = 12;
const INFRA = "Shared infrastructure";

type Box = { x: number; y: number };
type Band = { team: string; label: string; onCall?: string; y: number; h: number; hot: boolean };

function tiers(nodes: GraphNode[], edges: GraphEdge[]): Record<string, number> {
  const tier: Record<string, number> = Object.fromEntries(nodes.map((n) => [n.id, 0]));
  for (let pass = 0; pass < nodes.length; pass++) {
    let moved = false;
    for (const e of edges) {
      if (tier[e.target] < tier[e.source] + 1 && tier[e.source] + 1 < 8) { tier[e.target] = tier[e.source] + 1; moved = true; }
    }
    if (!moved) break;
  }
  return tier;
}

function layout(nodes: GraphNode[], edges: GraphEdge[], teams: Team[], journeys: Journey[], hot: Set<string>) {
  const tier = tiers(nodes, edges);
  const owner: Record<string, Team> = {};
  for (const t of teams) for (const s of t.owns) owner[s] = t;
  const laneOf = (n: GraphNode) => (n.labels.includes("Service") && owner[n.id] ? owner[n.id].name : INFRA);
  const lanes: Record<string, GraphNode[]> = {};
  for (const n of nodes) (lanes[laneOf(n)] ??= []).push(n);
  // customer-facing teams first: order lanes by the earliest tier of their services, infrastructure last
  // (the lane holding the website entry first, then by earliest tier, bigger lanes before smaller ones)
  const first = (lane: string) => Math.min(...(lanes[lane] ?? []).map((n) => tier[n.id]), 99);
  const entry = (lane: string) => ((lanes[lane] ?? []).some((n) => n.id === "frontend-proxy") ? 0 : 1);
  const size = (lane: string) => lanes[lane]?.length ?? 0;
  const order = [...teams.map((t) => t.name).sort((a, b) =>
    entry(a) - entry(b) || first(a) - first(b) || size(b) - size(a) || a.localeCompare(b)), INFRA];

  const sx = PAD + JW + GAP;
  const pos: Record<string, Box> = {};
  const bands: Band[] = [];
  let y = PAD + 22;
  for (const lane of order) {
    const members = lanes[lane];
    if (!members?.length) continue;
    const byTier: Record<number, GraphNode[]> = {};
    for (const n of [...members].sort((a, b) => a.id.localeCompare(b.id))) (byTier[tier[n.id]] ??= []).push(n);
    const rows = Math.max(...Object.values(byTier).map((l) => l.length));
    for (const [t, list] of Object.entries(byTier)) {
      list.forEach((n, i) => (pos[n.id] = { x: sx + Number(t) * COL, y: y + BAND_HEAD + i * ROW }));
    }
    const h = BAND_HEAD + rows * ROW - (ROW - H) + 12;
    const team = teams.find((t) => t.name === lane);
    bands.push({ team: lane, label: lane === INFRA ? INFRA : `${lane} team`, onCall: team?.on_call[0], y, h,
                 hot: members.some((n) => hot.has(n.id)) });
    y += h + BAND_GAP;
  }
  const maxTier = Math.max(0, ...nodes.map((n) => tier[n.id]));
  const width = sx + maxTier * COL + W + PAD + 8;
  const height = Math.max(y - BAND_GAP + PAD, PAD + 22 + journeys.length * (JH + 14) + PAD);
  // customers: centred against the lanes
  const jTotal = journeys.length * (JH + 14) - 14;
  const jy0 = Math.max(PAD + 22, (height - jTotal) / 2);
  const jpos: Record<string, Box> = {};
  journeys.forEach((j, i) => (jpos[j.id] = { x: PAD, y: jy0 + i * (JH + 14) }));
  return { pos, jpos, bands, width, height, sx };
}

function curve(x1: number, y1: number, x2: number, y2: number): string {
  const dx = Math.max(30, (x2 - x1) / 2);
  return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
}

function edgePath(a: Box, b: Box): string {
  if (b.x > a.x) return curve(a.x + W, a.y + H / 2, b.x, b.y + H / 2);
  const x1 = a.x + W / 2, y1 = a.y + H, x2 = b.x + W / 2, y2 = b.y; // same column: drop down/up between cards
  return y2 > y1 ? `M${x1},${y1} C${x1 + 40},${y1 + 20} ${x2 + 40},${y2 - 20} ${x2},${y2}`
    : `M${x1},${a.y} C${x1 + 50},${a.y - 30} ${x2 + 50},${b.y + H + 30} ${x2},${b.y + H}`;
}

const rateOf = (e: GraphEdge) => e.rps ?? e.rate ?? 0;
const fmtRate = (v?: number | null) => (v == null ? "–" : v >= 10 ? Math.round(v).toString() : v >= 1 ? v.toFixed(1) : v.toFixed(2));
export const perHour = (rps?: number | null) => {
  const h = (rps ?? 0) * 3600;
  return h >= 1000 ? `${(h / 1000).toFixed(1)}k` : `${Math.round(h)}`;
};
/** "hurt": the journey's success rate fell 5+ points under its normal; "risk": it critically needs the root cause. */
export function journeyState(j: Journey, root?: string | null): "hurt" | "risk" | "ok" {
  const drop = (j.baseline ?? 1) - (j.success_rate ?? 1);
  if (drop >= 0.05) return "hurt";
  return root && j.needs.includes(root) ? "risk" : "ok";
}

export default function ServiceMap({ graph, overlay }: { graph: Graph | null; overlay: Overlay }) {
  const root = overlay.root?.startsWith("edge:") ? overlay.root.split("->")[1] : overlay.root;
  const rootEdge = overlay.root?.startsWith("edge:") ? overlay.root.slice(5) : null;
  const hotKey = (graph?.nodes ?? []).filter((n) => n.labels.includes("Anomalous")).map((n) => n.id).sort().join();

  const view = useMemo(() => {
    const keep = (graph?.nodes ?? []).filter((n) => !HIDDEN.has(n.id));
    const ids = new Set(keep.map((n) => n.id));
    const flows = (graph?.edges ?? []).filter((e) => FLOW.has(e.type) && ids.has(e.source) && ids.has(e.target) && e.source !== e.target);
    const linked = new Set(flows.flatMap((e) => [e.source, e.target]));
    const nodes = keep.filter((n) => linked.has(n.id) || (n.rps ?? 0) > 0);
    const hot = new Set(nodes.filter((n) => n.labels.includes("Anomalous")).map((n) => n.id));
    const journeys = (graph?.journeys ?? []).filter((j) => (j.rps ?? 0) > 0 || j.needs.length > 0)
      .sort((a, b) => (b.rps ?? 0) - (a.rps ?? 0));
    const entry = nodes.find((n) => n.id === "frontend-proxy") ?? nodes.find((n) => n.id === "frontend");
    return { nodes, flows, hot, journeys, entry, ...layout(nodes, flows, graph?.teams ?? [], journeys, hot) };
  }, [graph, hotKey]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!graph) return <div className="grid h-full place-items-center text-sm muted">Connecting to RootCause…</div>;
  if (view.nodes.length === 0) return <div className="grid h-full place-items-center text-sm muted">Waiting for the first traces…</div>;

  const { nodes, flows, hot, journeys, entry, pos, jpos, bands, width, height, sx } = view;
  const incident = !!root;
  const onPath = (e: GraphEdge) => {
    const p = overlay.path ?? [];
    const i = p.indexOf(e.source);
    return i >= 0 && p[i + 1] === e.target;
  };

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" preserveAspectRatio="xMidYMid meet" role="img"
         aria-label="Company map: customers, the services each team owns, and the calls between them">
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#3B4A66" />
        </marker>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" /></filter>
      </defs>

      {/* column headings */}
      <text x={PAD} y={PAD + 6} fontSize={11} fontWeight={700} letterSpacing="0.1em" fill={C.pineSoft}>CUSTOMERS</text>
      <text x={sx - 14} y={PAD + 6} fontSize={11} fontWeight={700} letterSpacing="0.1em" fill={C.pineSoft}>TEAMS AND THE SERVICES THEY RUN</text>

      {/* team lanes */}
      {bands.map((b) => (
        <g key={b.team}>
          <rect x={sx - 14} y={b.y} width={width - sx - PAD + 14} height={b.h} rx={14}
                fill={b.hot ? "rgba(244,63,94,0.06)" : "rgba(148,163,184,0.04)"}
                stroke={b.hot ? "rgba(244,63,94,0.45)" : "rgba(148,163,184,0.14)"} strokeWidth={1} />
          <text x={sx - 2} y={b.y + 17} fontSize={11.5} fill={b.hot ? C.raspberry : C.pineSoft}>
            <tspan fontWeight={700} letterSpacing="0.06em">{b.label.toUpperCase()}</tspan>
            {b.onCall && <tspan dx={8}>· on call: {b.onCall}{b.hot ? " · affected" : ""}</tspan>}
          </text>
        </g>
      ))}

      {/* customers -> the website */}
      {entry && pos[entry.id] && journeys.map((j) => {
        const a = jpos[j.id], b = pos[entry.id];
        const js = journeyState(j, root);
        const hurt = js !== "ok";
        const d = curve(a.x + JW, a.y + JH / 2, b.x, b.y + H / 2);
        const dots = (j.rps ?? 0) > 0 ? Math.min(4, 1 + Math.floor(Math.log2(1 + (j.rps ?? 0) * 6))) : 0;
        const failing = 1 - (j.success_rate ?? 1);
        const red = hurt && failing > 0.02 ? Math.max(1, Math.round(dots * failing)) : 0;
        return (
          <g key={`j>${j.id}`}>
            <path d={d} fill="none" stroke={js === "hurt" ? C.raspberry : js === "risk" ? C.saffron : "#2A3A57"} strokeWidth={hurt ? 2 : 1.4} opacity={hurt ? 0.9 : 0.8}
                  strokeDasharray={hurt ? "6 5" : undefined} className={hurt ? "evidence-flow" : undefined} />
            {Array.from({ length: dots }, (_, i) => (
              <circle key={i} r={2.6} fill={i < red ? C.raspberry : C.eucalyptus}>
                <animateMotion dur="2.6s" begin={`${(-i * 2.6) / dots}s`} repeatCount="indefinite" path={d} />
              </circle>
            ))}
          </g>
        );
      })}

      {/* calls between services */}
      {flows.map((e) => {
        const a = pos[e.source], b = pos[e.target];
        if (!a || !b) return null;
        const d = edgePath(a, b);
        const r = rateOf(e);
        const err = e.err_rate ?? 0;
        const path = onPath(e) || rootEdge === `${e.source}->${e.target}`;
        const involved = path || (hot.has(e.source) && hot.has(e.target));
        const dim = incident && !involved;
        const stroke = path ? C.raspberry : err >= 0.01 ? errColour(err) : "#2A3A57";
        const w = path ? 3 : 1 + Math.min(3, Math.log2(1 + r * 3));
        const dots = r <= 0 ? 0 : Math.min(5, 1 + Math.floor(Math.log2(1 + r * 2)));
        const red = err >= 0.05 ? Math.max(1, Math.round(dots * err)) : 0;
        const dur = r > 5 ? 1.6 : r > 1 ? 2.4 : r > 0.2 ? 3.4 : 5;
        const async = e.type === "PRODUCES_TO" || e.type === "CONSUMED_BY";
        return (
          <g key={`${e.type}:${e.source}>${e.target}`} opacity={dim ? 0.22 : 1} style={{ transition: "opacity .6s" }}>
            <path d={d} fill="none" stroke={stroke} strokeWidth={w} strokeLinecap="round" markerEnd="url(#arrow)"
                  strokeDasharray={async ? "5 5" : path ? "10 6" : undefined} className={path ? "evidence-flow" : undefined}>
              <title>{`${nameOf(e.source)} → ${nameOf(e.target)}: ${fmtRate(r)} requests/s, ${Math.round(err * 100)} % failing`}</title>
            </path>
            {Array.from({ length: dots }, (_, i) => (
              <circle key={i} r={i < red ? 3.2 : 2.3} fill={i < red ? C.raspberry : C.eucalyptus} opacity={0.95}>
                <animateMotion dur={`${dur}s`} begin={`${(-i * dur) / dots}s`} repeatCount="indefinite" path={d} />
              </circle>
            ))}
          </g>
        );
      })}

      {/* customer cards */}
      {journeys.map((j) => {
        const p = jpos[j.id];
        const js = journeyState(j, root);
        const hurt = js === "hurt";
        const failing = 1 - (j.success_rate ?? 1);
        const tint = hurt ? C.raspberry : js === "risk" ? C.saffron : null;
        return (
          <g key={j.id} transform={`translate(${p.x},${p.y})`}>
            {tint && <rect x={-4} y={-4} width={JW + 8} height={JH + 8} rx={14} fill={tint} opacity={0.25} filter="url(#glow)" className="pulse-ring" />}
            <rect width={JW} height={JH} rx={12} fill={hurt ? "#2A1420" : js === "risk" ? "#2A220E" : C.card} stroke={tint ?? "#2C3B58"} />
            <text x={14} y={22} fontSize={14} fontWeight={600} fill={C.pine}>{j.name}</text>
            <text x={14} y={40} fontSize={12} fill={hurt ? "#FDA4AF" : js === "risk" ? "#FCD34D" : C.pineSoft}>
              {perHour(j.rps)} / hour{hurt ? ` · ${Math.round(failing * 100)} % failing` : js === "risk" ? " · at risk" : ""}
            </text>
            <title>{`${j.name}: about ${perHour(j.rps)} requests an hour, ${Math.round((j.success_rate ?? 1) * 100)} % succeed`}</title>
          </g>
        );
      })}

      {/* service cards */}
      {nodes.map((n) => {
        const p = pos[n.id];
        if (!p) return null;
        const isRoot = root === n.id;
        const alerting = hot.has(n.id);
        const ring = overlay.cited?.includes(n.id) ? "#FFFFFF" : overlay.predicted?.includes(n.id) ? C.plum
          : overlay.blast?.includes(n.id) ? C.lake : null;
        const err = n.err_rate ?? 0;
        const kind = n.labels.includes("Queue") ? "queue" : n.labels.includes("Datastore") ? "store" : "service";
        const sub = kind === "queue" ? `${n.id} · lag ${Math.round(n.lag ?? 0)}`
          : `${n.id.replace(/^(db|cache):/, "")} · ${fmtRate(n.rps)}/s${err >= 0.005 ? ` · ${Math.round(err * 100)}% err` : ""}`;
        const dim = incident && !alerting && !isRoot && !overlay.path?.includes(n.id) && !ring;
        const name = nameOf(n.id);
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.4 : 1} style={{ transition: "opacity .6s" }}>
            {(alerting || isRoot) && <rect x={-5} y={-5} width={W + 10} height={H + 10} rx={14} fill={isRoot ? C.raspberry : C.saffron}
                                           opacity={isRoot ? 0.45 : 0.3} filter="url(#glow)" className="pulse-ring" />}
            {ring && <rect x={-6} y={-6} width={W + 12} height={H + 12} rx={15} fill="none" stroke={ring} strokeWidth={2}
                           strokeDasharray={ring === C.plum ? "6 4" : undefined} />}
            <rect width={W} height={H} rx={kind === "store" ? 7 : 11}
                  fill={isRoot ? "#4C0F22" : alerting ? "#33260C" : C.card}
                  stroke={isRoot ? C.raspberry : alerting ? C.saffron : "#2C3B58"} strokeWidth={isRoot || alerting ? 1.8 : 1} />
            <circle cx={13} cy={17} r={4} fill={isRoot ? C.raspberry : alerting ? C.saffron : err >= 0.01 ? C.saffron : C.eucalyptus} />
            <text x={24} y={21} fontSize={13.5} fontWeight={600} fill={C.pine}>{name.length > 17 ? `${name.slice(0, 16)}…` : name}</text>
            <text x={12} y={39} fontSize={11} fill={isRoot ? "#FDA4AF" : C.pineSoft} fontFamily="'JetBrains Mono', monospace">
              {sub.length > 24 ? `${sub.slice(0, 23)}…` : sub}
            </text>
            {isRoot && <text x={W - 8} y={-9} fontSize={10.5} fontWeight={700} textAnchor="end" fill={C.raspberry} letterSpacing="0.08em">ROOT CAUSE</text>}
            <title>{`${name} (${n.id})\n${fmtRate(n.rps)} requests/s\n${Math.round(err * 1000) / 10} % errors${n.p95_ms != null ? `\np95 ${Math.round(n.p95_ms)} ms` : ""}${alerting ? "\nALERTING" : ""}${isRoot ? "\nROOT CAUSE" : ""}`}</title>
          </g>
        );
      })}
    </svg>
  );
}
