// RootCause UI. Left: the shop's live service map with its vital signs. Right: the incident told as a story
// (what broke, why, who is hurt, "should I fix this?", the fix step by step, back to normal) plus the other tabs.
// Everything shown is the real state of the graph (GET /api/graph, /api/incidents/{id}) pushed over SSE every tick.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Graph, Incident, Status } from "./api";
import { api, subscribe } from "./api";
import HealthStrip, { healthOf, type HealthPoint, type Marker } from "./components/HealthStrip";
import ServiceMap from "./components/ServiceMap";
import Story from "./components/Story";
import { C } from "./palette";
import ChaosLab, { type ChaosRun } from "./tabs/ChaosLab";
import Memory from "./tabs/Memory";
import Predict from "./tabs/Predict";
import Reports from "./tabs/Reports";

const TABS = ["Incident", "Break something", "Predict", "Memory", "Reports"] as const;
type Tab = (typeof TABS)[number];
const HISTORY = 90; // ticks kept for the timeline (~7.5 min)

export default function App() {
  const [tab, setTab] = useState<Tab>("Incident");
  const [status, setStatus] = useState<Status | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [history, setHistory] = useState<HealthPoint[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [inc, setInc] = useState<Incident | null>(null);
  const [reportReady, setReportReady] = useState(false);
  const [cited, setCited] = useState<string[]>([]);
  const [predicted, setPredicted] = useState<string[]>([]);
  const [blast, setBlast] = useState<string[]>([]);
  const [runs, setRuns] = useState<ChaosRun[]>([]);
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [restarting, setRestarting] = useState(false);
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selected;

  const onGraph = useCallback((g: Graph) => {
    setGraph(g);
    setHistory((h) => [...h, healthOf(g)].slice(-HISTORY));
  }, []);

  const refreshIncidents = useCallback(async () => {
    const list = await api.incidents("all").catch(() => [] as Incident[]);
    setIncidents(list);
    // follow the biggest open incident; otherwise stay on the one being looked at (its "fixed" ending)
    const open = list.filter((i) => i.status === "open").sort((a, b) => (b.members?.length ?? 0) - (a.members?.length ?? 0));
    setSelected((cur) => {
      const still = list.find((i) => i.id === cur);
      if (open[0] && (!still || still.status !== "open")) {
        const justFixed = still?.status === "resolved" && Date.now() - (still.resolved_ts ?? 0) < 3 * 60_000;
        if (!justFixed || (open[0].members?.length ?? 0) > 1) return open[0].id;
      }
      return still ? cur : open[0]?.id ?? list[0]?.id ?? null;
    });
  }, []);

  const refreshIncident = useCallback(async () => {
    const id = selectedRef.current;
    if (!id) { setInc(null); return; }
    const full = await api.incident(id).catch(() => null);
    setInc(full);
    if (full?.status === "resolved") {
      const reports = await api.reports().catch(() => []);
      setReportReady(reports.some((r) => r.incident === id));
    } else setReportReady(false);
  }, []);

  useEffect(() => {
    api.status().then(setStatus).catch(() => {});
    api.graph().then(onGraph).catch(() => {});
    api.scenarios().then(setScenarios).catch(() => {});
    refreshIncidents();
    return subscribe({
      tick: setStatus,
      graph_delta: onGraph,
      alert: () => refreshIncidents(),
      incident: () => { refreshIncidents(); refreshIncident(); },
      step: () => refreshIncident(),
      action: () => refreshIncident(),
      report: () => refreshIncident(),
      chaos_run: (r: ChaosRun) => setRuns((rs) => [r, ...rs]),
    });
  }, [onGraph, refreshIncidents, refreshIncident]);

  // refresh the open incident every tick too: alerts clearing during recovery do not emit an incident event
  useEffect(() => { refreshIncident(); }, [selected, status?.tick, refreshIncident]);

  async function startRunThrough() {
    const name = status?.replay?.scenario ?? scenarios[0];
    if (!name) return;
    setRestarting(true);
    try {
      await api.startReplay(name);
      setHistory([]); setSelected(null); setInc(null); setIncidents([]); setBlast([]); setCited([]); setTab("Incident");
    } finally { setTimeout(() => setRestarting(false), 3000); }
  }

  const open = inc?.status === "open";
  const fixing = !!inc?.actions.some((a) => ["approved", "executing", "executed"].includes(a.status));
  const recentlyFixed = inc?.status === "resolved" && Date.now() - (inc.resolved_ts ?? 0) < 5 * 60_000;
  const state = (status?.learning_left_ms ?? 0) > 0 ? "learning" : open ? (fixing ? "fixing" : "incident") : recentlyFixed ? "recovered" : "healthy";

  const overlay = useMemo(() => ({
    root: open || fixing ? inc?.root_target ?? null : null,
    path: tab === "Incident" && open ? inc?.evidence_path : undefined,
    cited, blast,
    predicted: tab === "Predict" ? predicted : undefined,
  }), [open, fixing, inc?.root_target, inc?.evidence_path, tab, cited, blast, predicted]);

  const markers: Marker[] = useMemo(() => {
    if (!inc) return [];
    const m: Marker[] = [{ ts: inc.created_ts, label: "incident", colour: C.raspberry }];
    const applied = inc.actions.find((a) => a.executed_ts);
    if (applied?.executed_ts) m.push({ ts: applied.executed_ts, label: "fix applied", colour: C.pine });
    if (inc.resolved_ts) m.push({ ts: inc.resolved_ts, label: "resolved", colour: C.eucalyptus });
    return m;
  }, [inc]);

  const replay = status?.mode === "replay";
  const others = incidents.filter((i) => i.id !== selected).slice(0, 6);

  return (
    <div className="min-h-full bg-porcelain">
      <header className="border-b border-pine/10 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
          <div className="flex items-baseline gap-3">
            <h1 className="font-display text-2xl font-extrabold tracking-[-0.03em]">RootCause</h1>
            <span className="hidden text-sm muted md:inline">the AI on-call engineer for the OpenTelemetry Demo shop</span>
          </div>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold tracking-wide ${replay ? "bg-plum/15 text-plum" : "bg-eucalyptus/20 text-pine"}`}>
            {!status ? "CONNECTING" : replay ? "REPLAY" : "LIVE"}
          </span>
          <nav className="no-scrollbar order-last flex w-full gap-1 overflow-x-auto lg:order-none lg:ml-auto lg:w-auto">
            {TABS.map((t) => (
              <button key={t} onClick={() => setTab(t)} aria-pressed={tab === t}
                      className={`shrink-0 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-medium transition ${tab === t ? "bg-pine text-paper" : "hover:bg-pine/5"}`}>{t}</button>
            ))}
          </nav>
          {replay && (
            <button className="btn-primary ml-auto lg:ml-0" disabled={restarting} onClick={startRunThrough}>
              {restarting ? "Restarting…" : "▶ Run-through from the start"}
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto grid max-w-[1600px] gap-5 p-4 md:p-5 lg:grid-cols-[minmax(0,1fr)_460px]">
        <section className="flex min-w-0 flex-col gap-4">
          <div className="sheet p-4"><HealthStrip history={history} markers={markers} state={state} /></div>
          <div className="sheet flex min-h-[420px] flex-col p-4 lg:h-[calc(100vh-250px)]">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-display text-lg font-bold">The shop, live from the graph</h2>
              <p className="text-xs muted">
                {status ? `${status.graph} · tick ${status.tick}` : ""}{replay && status?.replay ? ` · recorded incident (${status.replay.phase})` : ""}
              </p>
            </div>
            {/* phones: keep the map readable and let it scroll sideways */}
            <div className="min-h-0 flex-1 overflow-x-auto"><div className="h-full min-w-[860px] lg:min-w-0">
              <ServiceMap graph={graph} overlay={overlay} />
            </div></div>
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs muted">
              <li className="flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-eucalyptus" />healthy</li>
              <li className="flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-saffron" />alerting</li>
              <li className="flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-raspberry" />root cause / failing requests</li>
              <li className="flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full border-2 border-lake" />touched by the fix</li>
              {tab === "Predict" && <li className="flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full border-2 border-plum" />predicted to fail</li>}
            </ul>
          </div>
          {replay && (
            <p className="px-1 text-xs muted">
              Replay: real telemetry recorded from the OpenTelemetry Demo is fed through the real RootCause engine, so every
              alert, diagnosis and step here is computed live. Applying a fix is simulated; the recovery that follows is the one
              recorded on the real demo.
            </p>
          )}
        </section>

        <aside className="sheet min-w-0 p-5 lg:h-[calc(100vh-110px)] lg:overflow-y-auto">
          {tab === "Incident" && (
            <>
              <div className="mb-5 flex items-center justify-between gap-3">
                <h2 className="font-display text-2xl font-bold tracking-tight">{inc ? `Incident ${inc.id}` : "No incident"}</h2>
                {others.length > 0 && (
                  <select className="field max-w-[180px] py-1 text-xs" value="" aria-label="Open another incident"
                          onChange={(e) => e.target.value && setSelected(e.target.value)}>
                    <option value="">Other incidents…</option>
                    {others.map((i) => <option key={i.id} value={i.id}>{i.id} · {i.status}{i.root_target ? ` · ${i.root_target}` : ""}</option>)}
                  </select>
                )}
              </div>
              <Story status={status} inc={inc} reportReady={reportReady} onChanged={refreshIncident} onCite={setCited}
                     onBlast={setBlast} onOpenReport={() => setTab("Reports")} onStart={replay ? startRunThrough : undefined} />
            </>
          )}
          {tab === "Break something" && <ChaosLab status={status} runs={runs} />}
          {tab === "Predict" && <Predict graph={graph} onOverlay={setPredicted} />}
          {tab === "Memory" && <Memory />}
          {tab === "Reports" && <Reports />}
        </aside>
      </main>
    </div>
  );
}
