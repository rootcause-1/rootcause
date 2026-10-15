// RootCause UI: header (LIVE/REPLAY, graph, tick), live graph + incident panel + agent trail, and the tabs.
import { useCallback, useEffect, useState } from "react";
import type { Graph, Incident, Status } from "./api";
import { api, clock, subscribe } from "./api";
import GraphView, { type Overlays } from "./components/GraphView";
import IncidentPanel from "./components/IncidentPanel";
import TrailDrawer from "./components/TrailDrawer";
import ChaosLab, { type ChaosRun } from "./tabs/ChaosLab";
import Memory from "./tabs/Memory";
import Predict from "./tabs/Predict";
import Reports from "./tabs/Reports";

const TABS = ["Incident", "Chaos lab", "Predict", "Memory", "Reports"] as const;
type Tab = (typeof TABS)[number];

// what a first-time visitor of the public replay site should know in each phase
const REPLAY_HINT: Record<string, string> = {
  warming: "fast-forwarding healthy traffic to learn baselines…",
  healthy: "healthy traffic…",
  broken: "a fault is live — watch the alerts become one incident, then approve the low-risk fix →",
  recovery: "fix applied — watching recovery",
  finished: "done — the scenario restarts in about 2 minutes",
};

export default function App() {
  const [tab, setTab] = useState<Tab>("Incident");
  const [status, setStatus] = useState<Status | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [inc, setInc] = useState<Incident | null>(null);
  const [cited, setCited] = useState<string[]>([]);
  const [predicted, setPredicted] = useState<string[]>([]);
  const [runs, setRuns] = useState<ChaosRun[]>([]);
  const [scenarios, setScenarios] = useState<string[]>([]);

  const refreshIncidents = useCallback(async () => {
    const list = await api.incidents("all").catch(() => []);
    setIncidents(list);
    setSelected((cur) => cur ?? list.find((i) => i.status === "open")?.id ?? list[0]?.id ?? null);
  }, []);
  const refreshIncident = useCallback(async () => {
    if (selected) setInc(await api.incident(selected).catch(() => null));
  }, [selected]);

  useEffect(() => {
    api.status().then(setStatus).catch(() => {});
    api.graph().then(setGraph).catch(() => {});
    api.scenarios().then(setScenarios).catch(() => {});
    refreshIncidents();
    return subscribe({
      tick: setStatus,
      graph_delta: setGraph,
      incident: () => refreshIncidents(),
      step: () => refreshIncident(),
      action: () => refreshIncident(),
      report: () => refreshIncident(),
      chaos_run: (r: ChaosRun) => setRuns((rs) => [r, ...rs]),
    });
  }, [refreshIncidents, refreshIncident]);

  useEffect(() => { refreshIncident(); }, [refreshIncident, incidents]);

  const overlays: Overlays = {
    path: tab === "Incident" ? inc?.evidence_path : undefined,
    cited,
    predicted: tab === "Predict" ? predicted : undefined,
  };
  const learning = status && status.learning_left_ms > 0;
  const mm = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, "0")}`;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-slate-800 px-4 py-2">
        <h1 className="text-lg font-bold tracking-tight">RootCause</h1>
        <span className={`rounded px-2 py-0.5 text-xs font-bold ${status?.mode === "replay" ? "bg-violet-700" : "bg-red-600"}`}>
          {status?.mode === "replay" ? "REPLAY" : "LIVE"}
        </span>
        <span className="font-mono text-xs text-slate-400">graph {status?.graph ?? "-"} · tick {status?.tick ?? 0} · {clock(status?.tick_ts)}</span>
        {status?.replay && <span className="text-xs text-violet-300">{status.replay.scenario}: {status.replay.phase}</span>}
        {status?.replay && (
          <span className="text-xs text-slate-300" title="Recorded from the real OpenTelemetry Demo; replayed through the same ingest and engine code.">
            {REPLAY_HINT[status.replay.phase] ?? ""}
          </span>
        )}
        {status?.mode === "replay" && scenarios.length > 0 && (
          <select className="rounded border border-slate-700 bg-slate-950 p-1 text-xs" defaultValue=""
                  onChange={(e) => e.target.value && api.startReplay(e.target.value)}>
            <option value="">scenario…</option>
            {scenarios.map((s) => <option key={s}>{s}</option>)}
          </select>
        )}
        {learning && <span className="text-xs text-amber-300">Learning baseline… {mm(status!.learning_left_ms)} left</span>}
        {status?.last_error && <span className="truncate text-xs text-red-400" title={status.last_error}>⚠ {status.last_error}</span>}
        <nav className="ml-auto flex gap-1">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)}
                    className={`rounded px-3 py-1 text-sm ${tab === t ? "bg-slate-700" : "hover:bg-slate-800"}`}>{t}</button>
          ))}
        </nav>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-12">
        <section className={`${tab === "Incident" ? "col-span-7" : "col-span-12 h-[45vh]"} min-h-0 border-r border-slate-800`}>
          {graph && graph.nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center text-slate-400">
              Waiting for traces… {learning ? `(learning baseline, ${mm(status!.learning_left_ms)} left)` : ""}
            </div>
          ) : <GraphView graph={graph} overlays={overlays} />}
        </section>
        {tab === "Incident" && (
          <aside className="col-span-5 flex min-h-0 flex-col gap-3 overflow-y-auto p-3">
            <div className="flex flex-wrap gap-1">
              {incidents.map((i) => (
                <button key={i.id} onClick={() => setSelected(i.id)}
                        className={`rounded px-2 py-0.5 font-mono text-xs ${selected === i.id ? "bg-slate-600" : "bg-slate-800"} ${i.status === "open" ? "text-red-300" : "text-slate-400"}`}>
                  {i.id}
                </button>
              ))}
              {incidents.length === 0 && <span className="text-sm text-slate-400">No incidents. All quiet.</span>}
            </div>
            {inc && <IncidentPanel inc={inc} onChanged={refreshIncident} />}
            {inc && <div className="h-72 shrink-0"><TrailDrawer steps={inc.steps} onHover={setCited} /></div>}
          </aside>
        )}
        {tab !== "Incident" && (
          <section className="col-span-12 overflow-y-auto">
            {tab === "Chaos lab" && <ChaosLab status={status} runs={runs} />}
            {tab === "Predict" && <Predict graph={graph} onOverlay={setPredicted} />}
            {tab === "Memory" && <Memory />}
            {tab === "Reports" && <Reports />}
          </section>
        )}
      </div>
    </div>
  );
}
