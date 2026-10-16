// Thin client for the RootCause API (/api/*) and its SSE stream.

export type GraphNode = {
  id: string; labels: string[]; rps?: number | null; err_rate?: number | null; p95_ms?: number | null;
  self_err_rate?: number | null; cpu_pct?: number | null; mem_mb?: number | null; lag?: number | null;
};
export type GraphEdge = {
  source: string; target: string; type: string; rps?: number | null; err_rate?: number | null;
  p95_ms?: number | null; rate?: number | null; weight?: number | null; protocol?: string | null;
};
export type Graph = { nodes: GraphNode[]; edges: GraphEdge[] };

export type Hypothesis = {
  target: string; score: number; rank: number; depth: number; self: number; pagerank: number;
  change: number; memory: number;
};
export type Action = {
  id: string; kind: string; target: string; risk: string; rank: number; status: string; reason: string;
  incident_id: string; params: Record<string, unknown>;
  side_effects: { affected_services?: string[]; affected_journeys?: string[]; stateful?: boolean; reason?: string };
};
export type Step = { id: string; n: number; tool: string; summary: string; ts: number; cited: string[] };
export type Incident = {
  id: string; status: string; members: string[]; root_target?: string; confidence?: number;
  created_ts: number; onset_ts: number; resolved_ts?: number; ttr_ms?: number; agent_state?: string;
  alerts: { id: string; kind: string; target: string; status: string; ts: number; value: number }[];
  hypotheses: Hypothesis[];
  changes: { id: string; kind: string; target: string; from_variant?: string; to?: string; ts: number; actor: string }[];
  impact: { journey: string; pct: number }[];
  steps: Step[]; actions: Action[]; evidence_path: string[];
  similar: { incident: string; score: number; fixes: string[]; root?: string }[];
  verdict?: { root_cause: string; narrative: string; fallback?: string } | null;
};
export type Status = {
  mode: string; graph: string; tick: number; tick_ts: number; learning_left_ms: number; agent_mode: string;
  spans_received: number; replay?: { scenario: string; phase: string; expected_fix: unknown } | null;
  chaos?: { running: boolean; done: number; total: number; current?: string | null; batch?: string | null };
  last_error?: string | null;
};

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { headers: { "content-type": "application/json" }, ...init });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ?? r.statusText);
  return body as T;
}

export const api = {
  status: () => j<Status>("/api/status"),
  graph: () => j<Graph>("/api/graph"),
  incidents: (status = "all") => j<Incident[]>(`/api/incidents?status=${status}`),
  incident: (id: string) => j<Incident>(`/api/incidents/${id}`),
  propose: (id: string) => j(`/api/incidents/${id}/propose`, { method: "POST" }),
  approve: (id: string, confirm?: string) =>
    j(`/api/actions/${id}/approve`, { method: "POST", body: JSON.stringify({ confirm, execute: true }) }),
  reject: (id: string) => j(`/api/actions/${id}/reject`, { method: "POST" }),
  blast: (node_id: string) =>
    j<{ node: string; upstream: string[]; journeys: string[] }>(`/api/blast/${encodeURIComponent(node_id)}`),
  predict: (node_id: string) =>
    j<{ id: string; services: string[]; queues: string[]; journeys: string[] }>("/api/predict", {
      method: "POST", body: JSON.stringify({ node_id }),
    }),
  scorePrediction: (id: string) =>
    j<{ precision: number; recall: number; predicted: string[]; actual: string[] }>(
      `/api/predictions/${id}/score`, { method: "POST" }),
  memory: () => j<{ id: string; root: string; ttr_ms: number; signals: string[]; fixes: string[]; similar: string[] }[]>(
    "/api/memory"),
  reports: () => j<{ id: string; incident: string; ts: number; markdown: string }[]>("/api/reports"),
  pager: () => j<{ ts: number; team: string; incident: string; message: string }[]>("/api/pager"),
  catalogue: () => j<{ flag: string; class: string }[]>("/api/chaos/catalogue"),
  chaosRun: (body: { n: number; flag?: string; mystery?: boolean }) =>
    j("/api/chaos/run", { method: "POST", body: JSON.stringify(body) }),
  scenarios: () => j<string[]>("/api/replay/scenarios"),
  startReplay: (scenario: string) =>
    j("/api/replay/start", { method: "POST", body: JSON.stringify({ scenario }) }),
};

export function subscribe(handlers: Record<string, (data: any) => void>): () => void {
  const es = new EventSource("/api/stream");
  for (const [event, fn] of Object.entries(handlers)) {
    es.addEventListener(event, (e) => fn(JSON.parse((e as MessageEvent).data)));
  }
  return () => es.close();
}

export const pct = (x?: number | null) => (x == null ? "-" : `${Math.round(x * 100)}%`);
export const clock = (ms?: number) => (ms ? new Date(ms).toLocaleTimeString() : "-");
