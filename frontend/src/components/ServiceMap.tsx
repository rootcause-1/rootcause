// The company map: the shop's customers on the left, the services grouped by the team that owns them (with who is on
// call), shared infrastructure at the bottom. Requests flow left -> right; one broken box visibly ripples out to the
// teams and the customers who depend on it. Drawn as small isometric boxes on paper, with requests as moving dots.
//
// Everything is the graph in FalkorDB, refreshed every 5 s (GET /api/graph: graph_nodes, graph_edges, graph_journeys,
// graph_teams):
// - lilac boxes = customers (Journey nodes: requests per hour, how many fail); a journey turns coral when its success
//   rate drops, amber "at risk" when it critically REQUIRES the root cause;
// - grey boxes = Service / Queue / Datastore nodes, in the lane of the Team that OWNS them;
// - dots travel along each CALLS / USES / messaging edge at its request rate; green = ok, coral = failing requests;
// - amber box = alerting (:Anomalous), coral box = root cause, dashed coral line = evidence path; floor rings:
//   lilac = touched by the fix, purple dashed = predicted to fail, dark = cited by the agent step you are hovering.
import { useMemo } from "react";
import type { Graph, GraphEdge, GraphNode, Journey, Team } from "../api";
import { C } from "../palette";

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

type Faces = readonly [string, string, string];

/** An isometric box centred on (cx, cy): top, left and right faces, with a status dot on top. */
function Cube({ cx, cy, s, faces, dot, pulse }: { cx: number; cy: number; s: number; faces: Faces; dot?: string; pulse?: boolean }) {
  const k = s * 0.866;
  const top = `${cx},${cy - s} ${cx + k},${cy - s / 2} ${cx},${cy} ${cx - k},${cy - s / 2}`;
  const left = `${cx - k},${cy - s / 2} ${cx},${cy} ${cx},${cy + s} ${cx - k},${cy + s / 2}`;
  const right = `${cx},${cy} ${cx + k},${cy - s / 2} ${cx + k},${cy + s / 2} ${cx},${cy + s}`;
  return (
    <g>
      <ellipse cx={cx} cy={cy + s + 1} rx={k + 3} ry={4} fill="#000" opacity={0.06} />
      <polygon points={left} fill={faces[1]} stroke="#00000014" strokeWidth={0.8} />
      <polygon points={right} fill={faces[2]} stroke="#00000014" strokeWidth={0.8} />
      <polygon points={top} fill={faces[0]} stroke="#00000014" strokeWidth={0.8} />
      {dot && <circle cx={cx} cy={cy - s / 2} r={3.4} fill={dot} className={pulse ? "pulse-ring" : undefined} />}
    </g>
  );
}

/** A ring on the floor under a box (blast radius, prediction, cited step, root halo). */
function FloorRing({ cx, cy, s, colour, dashed, pulse }: { cx: number; cy: number; s: number; colour: string; dashed?: boolean; pulse?: boolean }) {
  return <ellipse cx={cx} cy={cy + s * 0.55} rx={s * 1.55} ry={s * 0.75} fill="none" stroke={colour} strokeWidth={2}
                  strokeDasharray={dashed ? "5 4" : undefined} className={pulse ? "pulse-ring" : undefined} />;
}

const S = 15; // cube size
const CX = 20; // cube centre, from the left of a slot

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
  // edges leave from the end of a slot and arrive just left of the next box
  const into = (b: Box) => ({ x: b.x + CX - S - 4, y: b.y + H / 2 });
  const link = (a: Box, b: Box) => (b.x > a.x ? curve(a.x + W - 6, a.y + H / 2, into(b).x, into(b).y) : edgePath(a, b));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" preserveAspectRatio="xMidYMid meet" role="img"
         aria-label="Company map: customers, the services each team owns, and the calls between them">
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#BDB8A6" />
        </marker>
      </defs>

      <text x={PAD} y={PAD + 6} fontSize={10.5} fontWeight={500} letterSpacing="0.18em" fill={C.pineSoft}>CUSTOMERS</text>
      <text x={sx - 14} y={PAD + 6} fontSize={10.5} fontWeight={500} letterSpacing="0.18em" fill={C.pineSoft}>TEAMS AND THE SERVICES THEY RUN</text>

      {/* team lanes: a hairline and a label, washed coral when the team is affected */}
      {bands.map((b) => (
        <g key={b.team}>
          <rect x={sx - 14} y={b.y} width={width - sx - PAD + 14} height={b.h} rx={12}
                fill={b.hot ? "rgba(210,81,63,0.05)" : "rgba(255,255,255,0.4)"} stroke={b.hot ? "rgba(210,81,63,0.35)" : C.mist} />
          <text x={sx - 2} y={b.y + 17} fontSize={10.5} fill={b.hot ? C.raspberry : C.pineSoft}>
            <tspan fontWeight={600} letterSpacing="0.14em">{b.label.toUpperCase()}</tspan>
            {b.onCall && <tspan dx={10} fontFamily="'JetBrains Mono', monospace">on call · {b.onCall}{b.hot ? " · affected" : ""}</tspan>}
          </text>
        </g>
      ))}

      {/* customers -> the website */}
      {entry && pos[entry.id] && journeys.map((j) => {
        const a = jpos[j.id], b = pos[entry.id];
        const js = journeyState(j, root);
        const d = curve(a.x + JW - 4, a.y + JH / 2, into(b).x, into(b).y);
        const dots = (j.rps ?? 0) > 0 ? Math.min(4, 1 + Math.floor(Math.log2(1 + (j.rps ?? 0) * 6))) : 0;
        const failing = 1 - (j.success_rate ?? 1);
        const red = js === "hurt" ? Math.max(1, Math.round(dots * failing)) : 0;
        return (
          <g key={`j>${j.id}`}>
            <path d={d} fill="none" stroke={js === "hurt" ? C.raspberry : js === "risk" ? C.saffron : C.line}
                  strokeWidth={js === "ok" ? 1.2 : 1.8} strokeDasharray={js === "ok" ? undefined : "6 5"}
                  className={js === "ok" ? undefined : "evidence-flow"} />
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
        const d = link(a, b);
        const r = rateOf(e);
        const err = e.err_rate ?? 0;
        const path = onPath(e) || rootEdge === `${e.source}->${e.target}`;
        const involved = path || (hot.has(e.source) && hot.has(e.target));
        const dim = incident && !involved;
        const stroke = path || err >= 0.05 ? C.raspberry : err >= 0.01 ? C.saffron : C.line;
        const w = path ? 2.4 : 1 + Math.min(2, Math.log2(1 + r * 2) * 0.6);
        const dots = r <= 0 ? 0 : Math.min(5, 1 + Math.floor(Math.log2(1 + r * 2)));
        const red = err >= 0.05 ? Math.max(1, Math.round(dots * err)) : 0;
        const dur = r > 5 ? 1.8 : r > 1 ? 2.6 : r > 0.2 ? 3.6 : 5.2;
        const async = e.type === "PRODUCES_TO" || e.type === "CONSUMED_BY";
        return (
          <g key={`${e.type}:${e.source}>${e.target}`} opacity={dim ? 0.25 : 1} style={{ transition: "opacity .6s" }}>
            <path d={d} fill="none" stroke={stroke} strokeWidth={w} strokeLinecap="round" markerEnd="url(#arrow)"
                  strokeDasharray={async ? "4 4" : path ? "8 5" : undefined} className={path ? "evidence-flow" : undefined}>
              <title>{`${nameOf(e.source)} → ${nameOf(e.target)}: ${fmtRate(r)} requests/s, ${Math.round(err * 100)} % failing`}</title>
            </path>
            {Array.from({ length: dots }, (_, i) => (
              <circle key={i} r={i < red ? 3 : 2.3} fill={i < red ? C.raspberry : C.eucalyptus}>
                <animateMotion dur={`${dur}s`} begin={`${(-i * dur) / dots}s`} repeatCount="indefinite" path={d} />
              </circle>
            ))}
          </g>
        );
      })}

      {/* customers */}
      {journeys.map((j) => {
        const p = jpos[j.id];
        const js = journeyState(j, root);
        const failing = 1 - (j.success_rate ?? 1);
        const cy = p.y + JH / 2;
        const tone = js === "hurt" ? C.raspberry : js === "risk" ? C.saffron : undefined;
        return (
          <g key={j.id}>
            {tone && <FloorRing cx={p.x + CX} cy={cy} s={S} colour={tone} pulse />}
            <Cube cx={p.x + CX} cy={cy} s={S} faces={C.boxUser} dot={tone} pulse />
            <text x={p.x + 44} y={cy - 3} fontSize={13.5} fontWeight={600} fill={C.pine}>{j.name}</text>
            <text x={p.x + 44} y={cy + 13} fontSize={10.5} fontFamily="'JetBrains Mono', monospace" fill={tone ?? C.pineSoft}>
              {perHour(j.rps)}/hour{js === "hurt" ? ` · ${Math.round(failing * 100)}% fail` : js === "risk" ? " · at risk" : ""}
            </text>
            <title>{`${j.name}: about ${perHour(j.rps)} requests an hour, ${Math.round((j.success_rate ?? 1) * 100)} % succeed`}</title>
          </g>
        );
      })}

      {/* services */}
      {nodes.map((n) => {
        const p = pos[n.id];
        if (!p) return null;
        const isRoot = root === n.id;
        const alerting = hot.has(n.id);
        const err = n.err_rate ?? 0;
        const store = n.labels.includes("Datastore") || n.labels.includes("Queue");
        const cy = p.y + H / 2, cx = p.x + CX;
        const ring = overlay.cited?.includes(n.id) ? { c: C.pine, dashed: false } : overlay.predicted?.includes(n.id) ? { c: C.plum, dashed: true }
          : overlay.blast?.includes(n.id) ? { c: C.lake, dashed: false } : null;
        const dim = incident && !alerting && !isRoot && !overlay.path?.includes(n.id) && !ring;
        const name = nameOf(n.id);
        const sub = n.labels.includes("Queue") ? `${n.id} · lag ${Math.round(n.lag ?? 0)}`
          : `${n.id.replace(/^(db|cache):/, "")} · ${fmtRate(n.rps)}/s${err >= 0.005 ? ` · ${Math.round(err * 100)}%` : ""}`;
        return (
          <g key={n.id} opacity={dim ? 0.38 : 1} style={{ transition: "opacity .6s" }}>
            {isRoot && <FloorRing cx={cx} cy={cy} s={S + 4} colour={C.raspberry} pulse />}
            {ring && <FloorRing cx={cx} cy={cy} s={S + 1} colour={ring.c} dashed={ring.dashed} />}
            <Cube cx={cx} cy={cy} s={S} faces={isRoot ? C.boxRoot : alerting ? C.boxHot : store ? C.boxStore : C.boxIdle}
                  dot={isRoot ? C.raspberry : alerting || err >= 0.01 ? C.saffron : C.eucalyptus} pulse={isRoot || alerting} />
            {isRoot && <text x={p.x + 44} y={cy - 18} fontSize={9.5} fontWeight={600} letterSpacing="0.16em" fill={C.raspberry}>ROOT CAUSE</text>}
            <text x={p.x + 44} y={cy - 3} fontSize={13} fontWeight={600} fill={isRoot ? C.raspberry : C.pine}>
              {name.length > 16 ? `${name.slice(0, 15)}…` : name}
            </text>
            <text x={p.x + 44} y={cy + 12} fontSize={10} fontFamily="'JetBrains Mono', monospace" fill={isRoot ? C.raspberry : C.pineSoft}>
              {sub.length > 19 ? `${sub.slice(0, 18)}…` : sub}
            </text>
            <title>{`${name} (${n.id})\n${fmtRate(n.rps)} requests/s\n${Math.round(err * 1000) / 10} % errors${n.p95_ms != null ? `\np95 ${Math.round(n.p95_ms)} ms` : ""}${alerting ? "\nALERTING" : ""}${isRoot ? "\nROOT CAUSE" : ""}`}</title>
          </g>
        );
      })}
    </svg>
  );
}
