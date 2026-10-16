// RootCause UI: the 3D stage fills the window; a header, the title card, the incident dossier and the other tabs
// float over it on paper sheets. "Director" lets the camera follow the incident; "Film" (key F) hides the chrome
// for recording the demo.
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Graph, Incident, Status } from "./api";
import { api, subscribe } from "./api";
import IncidentPanel from "./components/IncidentPanel";
import TitleCard from "./components/TitleCard";
import Stage from "./scene/Stage";
import ChaosLab, { type ChaosRun } from "./tabs/ChaosLab";
import Memory from "./tabs/Memory";
import Predict from "./tabs/Predict";
import Reports from "./tabs/Reports";

const TABS = ["Incident", "Chaos lab", "Predict", "Memory", "Reports"] as const;
type Tab = (typeof TABS)[number];

// what a first-time visitor of the public replay site should know in each phase
const REPLAY_HINT: Record<string, string> = {
  warming: "Fast-forwarding healthy traffic to learn the baselines.",
  healthy: "Healthy traffic.",
  broken: "A fault is live. Watch the alerts collapse into one incident, then approve the fix.",
  recovery: "Fix applied. Watching the shop recover.",
  finished: "Recovered. The scenario starts again in about 2 minutes.",
  expired: "Nobody approved a fix, so the scenario is starting again.",
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
  const [picked, setPicked] = useState<string | null>(null);
  const [director, setDirector] = useState(true);
  const [film, setFilm] = useState(false);

  const refreshIncidents = useCallback(async () => {
    const list = await api.incidents("all").catch(() => []);
    setIncidents(list);
    // follow the biggest open incident (the storm), not whichever small one opened last
    const open = list.filter((i) => i.status === "open").sort((a, b) => (b.members?.length ?? 0) - (a.members?.length ?? 0));
    setSelected((cur) => {
      const still = list.find((i) => i.id === cur);
      const justFixed = still?.status === "resolved" && Date.now() - (still.resolved_ts ?? 0) < 3 * 60_000;
      // stay on an incident that was just fixed (its "Fixed." moment) unless a new multi-service incident starts
      if (open[0] && (!still || (still.status !== "open" && (!justFixed || (open[0].members?.length ?? 0) > 1)))) return open[0].id;
      const biggest = [...list.slice(0, 10)].sort((a, b) => (b.members?.length ?? 0) - (a.members?.length ?? 0))[0];
      return cur ?? biggest?.id ?? null;
    });
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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT" || (e.target as HTMLElement)?.tagName === "SELECT") return;
      if (e.key === "f" || e.key === "F") setFilm((f) => !f);
      if (e.key === "d" || e.key === "D") setDirector((d) => !d);
      if (e.key === "Escape") { setFilm(false); setPicked(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const incidentOpen = inc?.status === "open";
  const focus = useMemo(() => ({
    root: incidentOpen ? inc?.root_target : null,
    path: tab === "Incident" && incidentOpen ? inc?.evidence_path : undefined,
    cited,
    predicted: tab === "Predict" ? predicted : undefined,
  }), [incidentOpen, inc?.root_target, inc?.evidence_path, tab, cited, predicted]);

  const recent = incidents.filter((i) => i.status === "open").concat(incidents.filter((i) => i.status !== "open").slice(0, 8));
  const replay = status?.replay;

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="absolute inset-0">
        <Stage graph={graph} focus={focus} director={director} incidentOpen={!!incidentOpen}
               picked={picked} onPick={setPicked} frame={film ? 0 : tab === "Incident" ? 1 : -1} />
      </div>

      {!film && (
        <header className="pointer-events-none absolute inset-x-0 top-0 z-30 flex items-start gap-4 p-5">
          <div className="pointer-events-auto flex items-center gap-3">
            <h1 className="font-display text-[26px] font-extrabold tracking-[-0.03em]">RootCause</h1>
            <span className="flex items-center gap-2 rounded-full border border-pine/15 bg-paper/90 px-3 py-1 text-sm">
              <i className={`h-2 w-2 rounded-full ${status?.mode === "replay" ? "bg-plum" : "bg-eucalyptus"} motion-safe:animate-pulse`} />
              {!status ? "Connecting…" : status.mode === "replay" ? `Replay of ${replay?.scenario ?? "a recorded fault"}` : "Live on the OpenTelemetry Demo"}
            </span>
            {status?.mode === "replay" && scenarios.length > 0 && (
              <select className="field py-1 text-sm" defaultValue="" aria-label="Replay another recorded fault"
                      onChange={(e) => e.target.value && api.startReplay(e.target.value)}>
                <option value="">Replay another fault…</option>
                {scenarios.map((s) => <option key={s}>{s}</option>)}
              </select>
            )}
          </div>
          <nav className="pointer-events-auto ml-auto flex items-center gap-1 rounded-full border border-pine/10 bg-paper/90 p-1 backdrop-blur">
            {TABS.map((t) => (
              <button key={t} onClick={() => setTab(t)} aria-pressed={tab === t}
                      className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${tab === t ? "bg-pine text-paper" : "hover:bg-pine/5"}`}>{t}</button>
            ))}
          </nav>
          <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-pine/10 bg-paper/90 p-1">
            <button onClick={() => setDirector((d) => !d)} aria-pressed={director} title="Camera follows the incident (D)"
                    className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${director ? "bg-saffron/25" : "hover:bg-pine/5"}`}>
              Director {director ? "on" : "off"}
            </button>
            <button onClick={() => setFilm(true)} title="Hide the panels for recording (F)" className="rounded-full px-3.5 py-1.5 text-sm font-medium hover:bg-pine/5">
              Film
            </button>
          </div>
        </header>
      )}

      {replay && !film && (
        <p className="pointer-events-none absolute left-5 top-[68px] z-30 text-sm text-pine-soft">{REPLAY_HINT[replay.phase] ?? ""}</p>
      )}

      <div className={`pointer-events-none absolute bottom-8 left-8 z-20 ${tab === "Incident" ? "max-w-[46vw]" : "hidden"}`}>
        <TitleCard status={status} graph={graph} inc={inc} />
      </div>

      {!film && tab === "Incident" && (
        <aside className={`sheet absolute right-5 top-[84px] z-30 w-[440px] max-w-[calc(100%-40px)] overflow-y-auto p-6 ${inc ? "bottom-5" : ""}`}>
          {recent.length > 1 && (
            <select className="field mb-4 w-full" value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}
                    aria-label="Choose an incident">
              {recent.map((i) => <option key={i.id} value={i.id}>{i.id}, {i.status}{i.root_target ? `, ${i.root_target}` : ""}</option>)}
            </select>
          )}
          {inc ? <IncidentPanel inc={inc} onChanged={refreshIncident} onCite={setCited} />
               : <p className="text-[15px] muted">No incidents yet. When something breaks, the incident and its evidence appear here.</p>}
        </aside>
      )}

      {!film && tab !== "Incident" && (
        <section className="sheet absolute left-5 top-[84px] z-30 max-h-[calc(100%-104px)] w-[min(680px,calc(100%-40px))] overflow-y-auto p-6">
          {tab === "Chaos lab" && <ChaosLab status={status} runs={runs} />}
          {tab === "Predict" && <Predict graph={graph} onOverlay={setPredicted} />}
          {tab === "Memory" && <Memory />}
          {tab === "Reports" && <Reports />}
        </section>
      )}

      {film && (
        <button onClick={() => setFilm(false)} className="absolute right-5 top-5 z-30 rounded-full bg-paper/70 px-3 py-1 text-xs muted opacity-40 hover:opacity-100">
          Exit film (Esc)
        </button>
      )}
    </div>
  );
}
