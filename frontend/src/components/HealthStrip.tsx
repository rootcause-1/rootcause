// The shop's vital signs over the map: traffic, failing requests, alerts, and a timeline of failing requests with
// markers for "incident opened", "fix applied" and "resolved", so you can watch the errors spike and calm down.
// The history is only kept in the browser for drawing; every number comes from the graph snapshot of each tick.
import type { Graph } from "../api";
import { C } from "../palette";

export type HealthPoint = { ts: number; failed: number; requests: number; alerts: number };
export type Marker = { ts: number; label: string; colour: string };

const HIDDEN = new Set(["flagd", "flagd-ui", "load-generator", "frontend-web"]);

/** One point per tick: requests/s into the shop, failing requests/s summed over services, services alerting. */
export function healthOf(graph: Graph): HealthPoint {
  const services = graph.nodes.filter((n) => n.labels.includes("Service") && !HIDDEN.has(n.id));
  const entry = services.find((n) => n.id === "frontend-proxy") ?? services.reduce((a, b) => ((b.rps ?? 0) > (a?.rps ?? 0) ? b : a), services[0]);
  return {
    ts: Date.now(),
    requests: entry?.rps ?? 0,
    failed: services.reduce((s, n) => s + (n.rps ?? 0) * (n.err_rate ?? 0), 0),
    alerts: graph.nodes.filter((n) => n.labels.includes("Anomalous")).length,
  };
}

function Spark({ points, markers }: { points: HealthPoint[]; markers: Marker[] }) {
  const w = 360, h = 56;
  if (points.length < 2) return <div className="grid h-14 place-items-center text-xs muted">collecting…</div>;
  const t0 = points[0].ts, t1 = points[points.length - 1].ts;
  const max = Math.max(0.5, ...points.map((p) => p.failed));
  const x = (ts: number) => ((ts - t0) / Math.max(1, t1 - t0)) * w;
  const y = (v: number) => h - 4 - (v / max) * (h - 12);
  const line = points.map((p) => `${x(p.ts).toFixed(1)},${y(p.failed).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h + 12}`} className="h-[68px] w-full" aria-label="Failing requests over time">
      <polygon points={`0,${h - 4} ${line} ${w},${h - 4}`} fill={C.raspberry} opacity={0.12} />
      <polyline points={line} fill="none" stroke={C.raspberry} strokeWidth={2} strokeLinejoin="round" />
      <line x1={0} x2={w} y1={h - 4} y2={h - 4} stroke={C.mist} />
      {markers.filter((m) => m.ts >= t0 && m.ts <= t1).map((m) => (
        <g key={m.label + m.ts}>
          <line x1={x(m.ts)} x2={x(m.ts)} y1={0} y2={h - 4} stroke={m.colour} strokeWidth={1.5} strokeDasharray="3 3" />
          <text x={Math.min(w - 4, x(m.ts) + 3)} y={h + 9} fontSize={9} fill={m.colour} textAnchor={x(m.ts) > w - 60 ? "end" : "start"}>{m.label}</text>
        </g>
      ))}
    </svg>
  );
}

export default function HealthStrip({ history, markers, state }: {
  history: HealthPoint[]; markers: Marker[]; state: "learning" | "healthy" | "incident" | "fixing" | "recovered";
}) {
  const now = history[history.length - 1];
  const label = { learning: "Learning normal", healthy: "Healthy", incident: "Incident", fixing: "Fixing", recovered: "Recovered" }[state];
  const tone = state === "incident" ? "bg-raspberry text-paper" : state === "fixing" ? "bg-saffron text-pine"
    : state === "learning" ? "bg-mist text-pine" : "bg-eucalyptus text-paper";
  const kpi = (v: string, l: string, warn = false) => (
    <div><div className={`font-display text-2xl font-bold leading-none ${warn ? "text-raspberry" : ""}`}>{v}</div>
      <div className="mt-1 text-xs muted">{l}</div></div>
  );
  return (
    <div className="grid grid-cols-2 items-center gap-x-6 gap-y-3 sm:grid-cols-[auto_auto_auto_auto_1fr]">
      <span className={`w-fit rounded-full px-3 py-1 text-sm font-semibold ${tone}`}>{label}</span>
      {kpi(now ? now.requests.toFixed(1) : "–", "requests / s into the shop")}
      {kpi(now ? now.failed.toFixed(2) : "–", "failing requests / s", (now?.failed ?? 0) >= 0.05)}
      {kpi(now ? String(now.alerts) : "–", "services alerting", (now?.alerts ?? 0) > 0)}
      <div className="col-span-2 min-w-0 sm:col-span-1"><Spark points={history} markers={markers} /></div>
    </div>
  );
}
