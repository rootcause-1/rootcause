// The live service map: every service, queue and datastore of the shop as a labelled card, laid out in tiers so
// requests flow left -> right (callers on the left, their dependencies to the right).
//
// What you see is the graph in FalkorDB, refreshed every 5 s:
// - dots travel along each call edge; more dots = more traffic, red dots = the share of failing requests;
// - line colour = error rate on that call (green healthy, amber some errors, red failing);
// - card colour = state: white healthy, amber alerting (:Anomalous), red = the root cause;
// - rings: dashed amber = evidence path, blue = would be touched by the fix (blast radius),
//   plum = predicted to fail (Predict tab), dark = cited by the agent step you are hovering.
import { useMemo } from "react";
import type { Graph, GraphEdge, GraphNode } from "../api";
import { C, errColour } from "../palette";

export type Overlay = { root?: string | null; path?: string[]; cited?: string[]; predicted?: string[]; blast?: string[] };

const FLOW = new Set(["CALLS", "USES", "PRODUCES_TO", "CONSUMED_BY"]);
const HIDDEN = new Set(["flagd", "flagd-ui", "otel-collector"]); // infrastructure, not part of the shop's request flow
const NAMES: Record<string, string> = { "load-generator": "shoppers", "frontend-web": "browser" };
const W = 138, H = 50, COL = 172, ROW = 64, PAD = 16;

type Pos = Record<string, { x: number; y: number }>;

/** Tier = longest path from a source; within a tier, order by the mean position of callers (short edges). */
function layout(nodes: GraphNode[], edges: GraphEdge[]): { pos: Pos; width: number; height: number } {
  const ids = nodes.map((n) => n.id).sort();
  const preds: Record<string, string[]> = Object.fromEntries(ids.map((id) => [id, []]));
  for (const e of edges) preds[e.target]?.push(e.source);
  const tier: Record<string, number> = Object.fromEntries(ids.map((id) => [id, 0]));
  for (let pass = 0; pass < ids.length; pass++) {
    let moved = false;
    for (const e of edges) {
      if (tier[e.target] < tier[e.source] + 1 && tier[e.source] + 1 < 10) { tier[e.target] = tier[e.source] + 1; moved = true; }
    }
    if (!moved) break;
  }
  const tiers: string[][] = [];
  for (const id of ids) (tiers[tier[id]] ??= []).push(id);
  const order: Record<string, number> = {};
  tiers.forEach((t) => t?.forEach((id, i) => (order[id] = i)));
  for (let sweep = 0; sweep < 3; sweep++) {
    for (const t of tiers) {
      if (!t) continue;
      const bary = (id: string) => {
        const p = preds[id].filter((x) => order[x] !== undefined);
        return p.length ? p.reduce((s, x) => s + order[x], 0) / p.length : order[id];
      };
      t.sort((a, b) => bary(a) - bary(b) || a.localeCompare(b));
      t.forEach((id, i) => (order[id] = i));
    }
  }
  const tallest = Math.max(1, ...tiers.map((t) => t?.length ?? 0));
  const pos: Pos = {};
  tiers.forEach((t, ti) => t?.forEach((id, i) => {
    pos[id] = { x: PAD + ti * COL, y: PAD + (i + (tallest - t.length) / 2) * ROW };
  }));
  return { pos, width: PAD * 2 + (tiers.length - 1) * COL + W, height: PAD * 2 + (tallest - 1) * ROW + H };
}

function edgePath(a: { x: number; y: number }, b: { x: number; y: number }): string {
  if (b.x > a.x) { // forward: right side of the caller to the left side of the callee
    const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, dx = (x2 - x1) / 2;
    return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
  }
  // same tier or backwards: loop out under the cards
  const x1 = a.x + W / 2, y1 = a.y + H, x2 = b.x + W / 2, y2 = b.y + H;
  return `M${x1},${y1} C${x1},${y1 + 40} ${x2},${y2 + 40} ${x2},${y2}`;
}

const rate = (e: GraphEdge) => e.rps ?? e.rate ?? 0;
const fmtRate = (v?: number | null) => (v == null ? "–" : v >= 10 ? Math.round(v).toString() : v >= 1 ? v.toFixed(1) : v.toFixed(2));

export default function ServiceMap({ graph, overlay, onPick }: { graph: Graph | null; overlay: Overlay; onPick?: (id: string) => void }) {
  const { nodes, flows, pos, width, height } = useMemo(() => {
    const all = graph?.nodes ?? [];
    const keep = all.filter((n) => !HIDDEN.has(n.id));
    const ids = new Set(keep.map((n) => n.id));
    const flows = (graph?.edges ?? []).filter((e) => FLOW.has(e.type) && ids.has(e.source) && ids.has(e.target) && e.source !== e.target);
    const linked = new Set(flows.flatMap((e) => [e.source, e.target]));
    const nodes = keep.filter((n) => linked.has(n.id) || (n.rps ?? 0) > 0);
    return { nodes, flows, ...layout(nodes, flows) };
  }, [graph]);

  const root = overlay.root?.startsWith("edge:") ? overlay.root.split("->")[1] : overlay.root;
  const rootEdge = overlay.root?.startsWith("edge:") ? overlay.root.slice(5) : null;
  const incident = !!root;
  const hot = new Set(nodes.filter((n) => n.labels.includes("Anomalous")).map((n) => n.id));
  const onPath = (e: GraphEdge) => {
    const p = overlay.path ?? [];
    const i = p.indexOf(e.source);
    return i >= 0 && p[i + 1] === e.target;
  };

  if (!graph) return <div className="grid h-full place-items-center text-sm muted">Connecting to RootCause…</div>;
  if (nodes.length === 0) return <div className="grid h-full place-items-center text-sm muted">Waiting for the first traces…</div>;

  return (
    <svg viewBox={`0 0 ${width} ${height + 20}`} className="h-full w-full" role="img"
         aria-label="Service map: services of the shop and the calls between them">
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse"
                orient="auto-start-reverse">
          <path d="M0,0 L8,4 L0,8 z" fill={C.mist} />
        </marker>
      </defs>

      {flows.map((e) => {
        const a = pos[e.source], b = pos[e.target];
        if (!a || !b) return null;
        const d = edgePath(a, b);
        const r = rate(e);
        const err = e.err_rate ?? 0;
        const path = onPath(e) || rootEdge === `${e.source}->${e.target}`;
        const involved = path || (hot.has(e.source) && hot.has(e.target));
        const dim = incident && !involved;
        const stroke = path ? C.raspberry : errColour(err);
        const width = path ? 3.5 : 1 + Math.min(4, Math.log2(1 + r * 3));
        const dots = r <= 0 ? 0 : Math.min(5, 1 + Math.floor(Math.log2(1 + r * 2)));
        const red = err >= 0.05 ? Math.max(1, Math.round(dots * err)) : 0;
        const dur = r > 5 ? 1.6 : r > 1 ? 2.4 : r > 0.2 ? 3.4 : 5;
        const async = e.type === "PRODUCES_TO" || e.type === "CONSUMED_BY";
        return (
          <g key={`${e.type}:${e.source}>${e.target}`} opacity={dim ? 0.25 : 1} style={{ transition: "opacity .6s" }}>
            <path d={d} fill="none" stroke={stroke} strokeWidth={width} strokeLinecap="round"
                  strokeDasharray={async ? "5 5" : path ? "10 6" : undefined} markerEnd="url(#arrow)"
                  className={path ? "evidence-flow" : undefined}>
              <title>{`${e.source} → ${e.target} (${e.type.toLowerCase()}): ${fmtRate(r)} req/s, ${Math.round(err * 100)} % failing`}</title>
            </path>
            {Array.from({ length: dots }, (_, i) => (
              <circle key={i} r={i < red ? 3.2 : 2.4} fill={i < red ? C.raspberry : C.eucalyptus}>
                <animateMotion dur={`${dur}s`} begin={`${(-i * dur) / dots}s`} repeatCount="indefinite" path={d} />
              </circle>
            ))}
          </g>
        );
      })}

      {nodes.map((n) => {
        const p = pos[n.id];
        const isRoot = root === n.id;
        const alerting = hot.has(n.id);
        const ring = overlay.cited?.includes(n.id) ? C.pine : overlay.predicted?.includes(n.id) ? C.plum
          : overlay.blast?.includes(n.id) ? C.lake : overlay.path?.includes(n.id) && !isRoot ? C.saffron : null;
        const kind = n.labels.includes("Queue") ? "queue" : n.labels.includes("Datastore") ? "datastore" : "service";
        const name = NAMES[n.id] ?? n.id.replace(/^(queue|db|cache):/, "");
        const err = n.err_rate ?? 0;
        const sub = kind === "queue" ? `queue${n.lag != null ? ` · lag ${Math.round(n.lag)}` : ""}`
          : `${fmtRate(n.rps)} req/s${err >= 0.005 ? ` · ${Math.round(err * 100)} % err` : ""}`;
        const dim = incident && !alerting && !isRoot && !overlay.path?.includes(n.id) && !ring;
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.45 : 1} style={{ transition: "opacity .6s" }}
             className={onPick ? "cursor-pointer" : undefined} onClick={() => onPick?.(n.id)}>
            {(alerting || isRoot) && <rect x={-4} y={-4} width={W + 8} height={H + 8} rx={14} fill="none"
                                           stroke={isRoot ? C.raspberry : C.saffron} strokeWidth={2} className="pulse-ring" />}
            {ring && <rect x={-7} y={-7} width={W + 14} height={H + 14} rx={16} fill="none" stroke={ring} strokeWidth={2.5}
                           strokeDasharray={ring === C.plum || ring === C.saffron ? "6 4" : undefined} />}
            <rect width={W} height={H} rx={kind === "datastore" ? 6 : 11}
                  fill={isRoot ? C.raspberry : alerting ? "#FDF1DC" : C.paper}
                  stroke={isRoot ? C.raspberry : alerting ? C.saffron : "#C9D3C6"} strokeWidth={alerting || isRoot ? 2 : 1} />
            <circle cx={13} cy={H / 2} r={5} fill={isRoot ? C.paper : alerting ? C.saffron : err >= 0.01 ? C.saffron : C.eucalyptus} />
            <text x={25} y={21} fontSize={14.5} fontWeight={600} fill={isRoot ? C.paper : C.pine}>
              {name.length > 14 ? `${name.slice(0, 13)}…` : name}
            </text>
            <text x={25} y={38} fontSize={12} fill={isRoot ? "#FFE3EC" : C.pineSoft}>
              {kind === "datastore" ? `${n.id.startsWith("cache:") ? "cache" : "db"} · ` : ""}{sub}
            </text>
            <title>{`${n.id}\n${fmtRate(n.rps)} requests/s\n${Math.round(err * 1000) / 10} % errors${n.p95_ms != null ? `\np95 ${Math.round(n.p95_ms)} ms` : ""}${alerting ? "\nALERTING" : ""}${isRoot ? "\nROOT CAUSE" : ""}`}</title>
          </g>
        );
      })}
      <text x={PAD} y={height + 14} fontSize={12} fill={C.pineSoft}>requests flow left → right · line thickness = traffic · red dots = failing requests</text>
    </svg>
  );
}
