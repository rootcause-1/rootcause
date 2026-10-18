// RootCause UI. The company map fills the screen; the incident is told by a narrator popup that advances on its own
// (components/Narrator.tsx), with the steps shown along the top and the shop's vital signs in the corner.
// The other tools (break something, predict, memory, reports) open in a drawer.
// Everything shown is the real state of the graph (GET /api/graph, /api/incidents/{id}) pushed over SSE every tick.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Graph, Incident, Status } from "./api";
import { api, subscribe } from "./api";
import HealthStrip, { healthOf, type Health, type HealthPoint, type Marker } from "./components/HealthStrip";
import Narrator, { Intro, STAGE_LABEL, STAGES, targetStage, useNarration } from "./components/Narrator";
import ServiceMap from "./components/ServiceMap";
import { C } from "./palette";
import ChaosLab, { type ChaosRun } from "./tabs/ChaosLab";
import Codebase from "./tabs/Codebase";
import CompanySetup from "./tabs/Company";
import Memory from "./tabs/Memory";
import Predict from "./tabs/Predict";
import Reports from "./tabs/Reports";

const TOOLS = ["Break something", "Predict", "Memory", "Reports", "Codebase", "Your company"] as const;
type Tool = (typeof TOOLS)[number];
const HISTORY = 72; // ticks kept for the timeline (6 min)

export default function App() {
  const [tool, setTool] = useState<Tool | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [history, setHistory] = useState<HealthPoint[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [inc, setInc] = useState<Incident | null>(null);
  const [cited, setCited] = useState<string[]>([]);
  const [predicted, setPredicted] = useState<string[]>([]);
  const [blast, setBlast] = useState<string[]>([]);
  const [runs, setRuns] = useState<ChaosRun[]>([]);
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [demo, setDemo] = useState(false);
  const [autoplay, setAutoplay] = useState(true);
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selected;

  const onGraph = useCallback((g: Graph) => {
    setGraph(g);
    setHistory((h) => [...h, healthOf(g)].slice(-HISTORY));
  }, []);

  const refreshIncidents = useCallback(async () => {
    const list = await api.incidents("all").catch(() => [] as Incident[]);
    // follow the biggest open incident; otherwise stay on the one being looked at (its "back to normal" ending)
    const open = list.filter((i) => i.status === "open").sort((a, b) => (b.members?.length ?? 0) - (a.members?.length ?? 0));
    setSelected((cur) => {
      const still = list.find((i) => i.id === cur);
      if (open[0] && (!still || still.status !== "open")) {
        const justFixed = still?.status === "resolved" && Date.now() - (still.resolved_ts ?? 0) < 2 * 60_000;
        if (!justFixed) return open[0].id;
      }
      return still ? cur : open[0]?.id ?? list[0]?.id ?? null;
    });
  }, []);

  const refreshIncident = useCallback(async () => {
    const id = selectedRef.current;
    setInc(id ? await api.incident(id).catch(() => null) : null);
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
  // refresh every tick too: alarms clearing during recovery do not emit an incident event
  useEffect(() => { refreshIncident(); }, [selected, status?.tick, refreshIncident]);

  async function startDemo() {
    const name = status?.replay?.scenario ?? scenarios.find((s) => s === "productCatalogLockContention") ?? scenarios[0];
    if (!name) return;
    await api.startReplay(name).catch(() => null);
    setHistory([]); setSelected(null); setInc(null); setBlast([]); setCited([]); setTool(null);
    setDemo(true); setAutoplay(true);
  }

  const target = targetStage(status, inc, demo);
  const stage = useNarration(target);
  const si = STAGES.indexOf(stage);
  const reveal = si >= STAGES.indexOf("root") && stage !== "recovered"; // the map keeps the answer until the narrator gets there
  const overlay = useMemo(() => ({
    root: reveal ? inc?.root_target ?? null : null,
    path: reveal ? inc?.evidence_path : undefined,
    cited, blast,
    predicted: tool === "Predict" ? predicted : undefined,
  }), [reveal, inc?.root_target, inc?.evidence_path, cited, blast, tool, predicted]);

  const markers: Marker[] = useMemo(() => {
    if (!inc) return [];
    const m: Marker[] = [{ ts: inc.created_ts, label: "incident", colour: C.raspberry }];
    const applied = inc.actions.find((a) => a.executed_ts);
    if (applied?.executed_ts) m.push({ ts: applied.executed_ts, label: "fix applied", colour: C.lake });
    if (inc.resolved_ts) m.push({ ts: inc.resolved_ts, label: "resolved", colour: C.eucalyptus });
    return m;
  }, [inc]);
  const health: Health = (status?.learning_left_ms ?? 0) > 0 ? "learning"
    : stage === "fixing" ? "fixing" : stage === "recovered" ? "recovered" : inc?.status === "open" ? "incident" : "healthy";

  const replay = status?.mode === "replay";
  const steps = STAGES.slice(1);

  return (
    <div className="relative h-full w-full overflow-hidden bg-porcelain">
      {/* the map is the page */}
      <div className={`absolute inset-0 overflow-auto px-4 pb-4 pt-[112px] md:px-6 ${stage === "intro" ? "" : "xl:pr-[430px] 2xl:pr-[500px]"}`}>
        <div className="h-full min-h-[560px] min-w-[1000px] xl:min-w-0"><ServiceMap graph={graph} overlay={overlay} /></div>
      </div>

      {/* top bar */}
      <header className="pointer-events-none absolute inset-x-0 top-0 z-30 flex flex-wrap items-center gap-3 bg-gradient-to-b from-porcelain via-porcelain/90 to-transparent px-4 pb-6 pt-3 md:px-6">
        <div className="pointer-events-auto flex w-full flex-wrap items-center gap-3 rounded-2xl border border-mist bg-white/80 px-4 py-2 backdrop-blur">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-raspberry" aria-hidden />
            <h1 className="text-[15px] font-semibold">RootCause</h1>
            <span className="hidden font-display text-[17px] italic muted sm:inline">on call</span>
          </div>
          <nav className="hidden items-center rounded-xl border border-mist bg-porcelain p-0.5 md:flex">
            {(["Map", ...TOOLS] as const).map((t) => {
              const on = t === "Map" ? tool === null : tool === t;
              return (
                <button key={t} onClick={() => setTool(t === "Map" ? null : tool === t ? null : (t as Tool))} aria-pressed={on}
                        className={`rounded-lg px-3 py-1 text-sm transition ${on ? "bg-white font-medium shadow-sm" : "muted hover:text-pine"}`}>{t}</button>
              );
            })}
          </nav>
          <span className="ml-auto hidden items-center gap-2 font-mono text-[11px] muted lg:flex">
            <i className={`h-1.5 w-1.5 rounded-full ${replay ? "bg-plum" : "bg-eucalyptus"}`} />
            {!status ? "connecting" : `${replay ? "replay" : "live"} · ${status.graph} · tick ${status.tick} · ${status.tick_ts ? new Date(status.tick_ts).toLocaleTimeString([], { hour12: false }) : "--"}`}
          </span>
          {replay && <button className="btn-primary ml-auto lg:ml-0" onClick={startDemo}>{demo ? "↺ Restart demo" : "▶ Start demo"}</button>}
        </div>
        {/* where we are in the story */}
        {stage !== "intro" && (
          <ol className="pointer-events-auto order-last flex w-full items-center gap-1 overflow-x-auto pt-1 no-scrollbar">
            {steps.map((s, i) => {
              const k = i + 1;
              const state = k < si ? "done" : k === si ? "now" : "next";
              return (
                <li key={s} className="flex shrink-0 items-center gap-1">
                  <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs transition ${
                    state === "now" ? "bg-eucalyptus font-medium text-white" : state === "done" ? "border border-mist bg-white text-pine" : "text-pine-soft/70"}`}>
                    {state === "done" ? "✓" : <span className="tabular-nums">{k}</span>} {STAGE_LABEL[s]}
                  </span>
                  {k < steps.length && <span className="h-px w-3 bg-mist" aria-hidden />}
                </li>
              );
            })}
          </ol>
        )}
      </header>

      {/* right column (wide screens): vital signs on top, the narrator popup at the bottom; on smaller screens the
          narrator floats over the bottom of the map */}
      {stage !== "intro" && (
        <div className="sheet absolute right-6 top-[112px] z-20 hidden w-[390px] p-4 xl:block 2xl:w-[460px]">
          <HealthStrip history={history} markers={markers} state={health} />
        </div>
      )}
      {stage === "intro" ? (
        <div className="absolute inset-x-4 top-1/2 z-30 mx-auto max-w-[580px] -translate-y-1/2"><Intro onStart={startDemo} /></div>
      ) : (
        <div className="absolute inset-x-3 bottom-3 z-30 h-[62vh] md:inset-x-auto md:right-6 md:top-[120px] xl:top-[290px] md:bottom-5 md:h-auto md:w-[400px] xl:w-[390px] 2xl:w-[460px]">
          <Narrator stage={stage} typing={STAGES.indexOf(target) > si} status={status} inc={inc} graph={graph} demo={demo} autoplay={autoplay}
                    onStart={startDemo} onAutoplay={setAutoplay} onChanged={refreshIncident} onCite={setCited}
                    onBlast={setBlast} onOpenReport={() => setTool("Reports")} />
        </div>
      )}
      {stage === "intro" && <div className="absolute inset-0 z-20 bg-porcelain/50 backdrop-blur-[2px]" aria-hidden />}

      {/* tools drawer */}
      {tool && (
        <aside className="sheet absolute bottom-4 right-4 top-[112px] z-40 w-[min(560px,calc(100%-32px))] overflow-y-auto p-6 md:right-6">
          <button className="absolute right-4 top-4 rounded-lg px-2 py-1 text-sm muted hover:bg-mist/50" onClick={() => setTool(null)} aria-label="Close">✕</button>
          {tool === "Break something" && <ChaosLab status={status} runs={runs} />}
          {tool === "Predict" && <Predict graph={graph} onOverlay={setPredicted} />}
          {tool === "Memory" && <Memory />}
          {tool === "Reports" && <Reports />}
          {tool === "Codebase" && <Codebase />}
          {tool === "Your company" && <CompanySetup replay={replay} />}
        </aside>
      )}
    </div>
  );
}
