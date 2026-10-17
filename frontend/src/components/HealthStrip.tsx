// The shop's vital signs (top right over the map): status, requests/s, failing requests/s, services alerting, and a
// timeline of failing requests with "incident / fix applied / resolved" markers, so you can watch the errors spike and
// calm down. The history is only kept in the browser for drawing; every number comes from the graph snapshot.
import type { Graph } from "../api";
import { C } from "../palette";

export type HealthPoint = { ts: number; failed: number; requests: number; alerts: number };
export type Marker = { ts: number; label: string; colour: string };
export type Health = "learning" | "healthy" | "incident" | "fixing" | "recovered";

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
  const w = 300, h = 44;
  if (points.length < 2) return <div className="grid h-[56px] place-items-center text-xs muted">collecting…</div>;
  const t0 = points[0].ts, t1 = points[points.length - 1].ts;
  const max = Math.max(0.5, ...points.map((p) => p.failed));
  const x = (ts: number) => ((ts - t0) / Math.max(1, t1 - t0)) * w;
  const y = (v: number) => h - 2 - (v / max) * (h - 8);
  const line = points.map((p) => `${x(p.ts).toFixed(1)},${y(p.failed).toFixed(1)}`).join(" ");
  const bad = points[points.length - 1].failed >= 0.05;
  return (
    <svg viewBox={`0 0 ${w} ${h + 12}`} className="h-[56px] w-full" aria-label="Failing requests over time">
      <polygon points={`0,${h - 2} ${line} ${w},${h - 2}`} fill={bad ? C.raspberry : C.eucalyptus} opacity={0.15} />
      <polyline points={line} fill="none" stroke={bad ? C.raspberry : C.eucalyptus} strokeWidth={2} strokeLinejoin="round" />
      {markers.filter((m) => m.ts >= t0 && m.ts <= t1).map((m) => (
        <g key={m.label + m.ts}>
          <line x1={x(m.ts)} x2={x(m.ts)} y1={0} y2={h - 2} stroke={m.colour} strokeWidth={1.5} strokeDasharray="3 3" />
          <text x={Math.min(w - 2, x(m.ts) + 3)} y={h + 10} fontSize={9.5} fill={m.colour} textAnchor={x(m.ts) > w - 60 ? "end" : "start"}>{m.label}</text>
        </g>
      ))}
    </svg>
  );
}

export default function HealthStrip({ history, markers, state }: { history: HealthPoint[]; markers: Marker[]; state: Health }) {
  const now = history[history.length - 1];
  const label = { learning: "Learning normal", healthy: "All systems normal", incident: "Incident in progress", fixing: "Fix in progress", recovered: "Recovered" }[state];
  const tone = state === "incident" ? "bg-raspberry" : state === "fixing" ? "bg-saffron" : state === "learning" ? "bg-pine-soft" : "bg-eucalyptus";
  // (status dot + label, then the numbers; same paper card as everything else)
  const kpi = (v: string, l: string, warn = false) => (
    <div><div className={`font-display text-[34px] leading-none tabular-nums ${warn ? "text-raspberry" : ""}`}>{v}</div>
      <div className="mt-1 text-[11px] leading-tight muted">{l}</div></div>
  );
  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <span className={`h-2.5 w-2.5 rounded-full ${tone} ${state === "incident" ? "animate-pulse" : ""}`} />{label}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3">
        {kpi(now ? now.requests.toFixed(1) : "–", "requests / s")}
        {kpi(now ? now.failed.toFixed(2) : "–", "failing / s", (now?.failed ?? 0) >= 0.05)}
        {kpi(now ? String(now.alerts) : "–", "alarms firing", (now?.alerts ?? 0) > 0)}
      </div>
      <p className="kicker mt-3">failing requests · last few minutes</p>
      <Spark points={history} markers={markers} />
    </div>
  );
}
