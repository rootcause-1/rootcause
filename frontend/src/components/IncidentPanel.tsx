// Incident panel: "N alerts, 1 incident", ranked hypotheses (stacked bars of the five weighted signals),
// what changed, journey impact, similar incidents, the agent verdict and the action cards.
import type { Hypothesis, Incident } from "../api";
import { clock, pct } from "../api";
import ActionCard from "./ActionCard";

const WEIGHTS: Record<string, number> = { depth: 0.3, self: 0.25, pagerank: 0.2, change: 0.15, memory: 0.1 };
const COLOURS: Record<string, string> = {
  depth: "bg-sky-500", self: "bg-rose-500", pagerank: "bg-violet-500", change: "bg-amber-400", memory: "bg-emerald-500",
};

function HypBar({ h }: { h: Hypothesis }) {
  return (
    <div className="mb-2">
      <div className="flex justify-between text-sm">
        <span className="font-mono">{h.rank}. {h.target}</span>
        <span className="font-mono text-slate-300">{h.score.toFixed(2)}</span>
      </div>
      <div className="mt-1 flex h-2.5 w-full overflow-hidden rounded bg-slate-800">
        {Object.keys(WEIGHTS).map((s) => (
          <div key={s} title={`${s} ${(h[s as keyof Hypothesis] as number).toFixed(2)}`}
               className={COLOURS[s]} style={{ width: `${(h[s as keyof Hypothesis] as number) * WEIGHTS[s] * 100}%` }} />
        ))}
      </div>
    </div>
  );
}

export default function IncidentPanel({ inc, onChanged }: { inc: Incident; onChanged: () => void }) {
  const open = inc.alerts.filter((a) => a.status === "firing").length;
  return (
    <div className="space-y-3">
      <div className="card">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">{inc.id}</h2>
          <span className={`rounded px-2 py-0.5 text-xs ${inc.status === "open" ? "bg-red-600" : "bg-emerald-700"}`}>
            {inc.status}{inc.agent_state ? ` · ${inc.agent_state}` : ""}
          </span>
        </div>
        <p className="mt-1 text-2xl font-bold">
          {inc.alerts.length} alerts <span className="text-slate-400">→</span> 1 incident
        </p>
        <p className="text-xs text-slate-400">{open} firing · opened {clock(inc.created_ts)}
          {inc.ttr_ms ? ` · resolved in ${Math.round(inc.ttr_ms / 1000)} s` : ""}</p>
        {inc.verdict?.narrative && <p className="mt-2 text-sm text-slate-200">{inc.verdict.narrative}</p>}
        {inc.evidence_path?.length > 0 && (
          <p className="mt-2 font-mono text-xs text-yellow-300">{inc.evidence_path.join(" → ")}</p>
        )}
      </div>

      <div className="card">
        <div className="label mb-2">Ranked root causes</div>
        {inc.hypotheses.slice(0, 5).map((h) => <HypBar key={h.target} h={h} />)}
        {inc.hypotheses.length === 0 && <p className="text-sm text-slate-400">ranking…</p>}
        <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-400">
          {Object.keys(WEIGHTS).map((s) => (
            <span key={s} className="flex items-center gap-1"><i className={`inline-block h-2 w-2 ${COLOURS[s]}`} />{s}</span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="card">
          <div className="label mb-1">What changed</div>
          {inc.changes.length === 0 && <p className="text-sm text-slate-400">nothing near onset</p>}
          {inc.changes.map((c) => (
            <p key={c.id} className="text-sm"><span className="font-mono">{c.target}</span> {c.from_variant ?? ""} → {c.to ?? c.kind}
              <span className="block text-xs text-slate-400">{clock(c.ts)} · {c.actor}</span></p>
          ))}
        </div>
        <div className="card">
          <div className="label mb-1">Journey impact</div>
          {inc.impact.length === 0 && <p className="text-sm text-slate-400">none measured</p>}
          {inc.impact.map((i) => (
            <div key={i.journey} className="mb-1 text-sm">
              <div className="flex justify-between"><span>{i.journey.replace("journey:", "")}</span><span>-{pct(i.pct)}</span></div>
              <div className="h-1.5 rounded bg-slate-800"><div className="h-1.5 rounded bg-red-500" style={{ width: pct(i.pct) }} /></div>
            </div>
          ))}
        </div>
      </div>

      {inc.similar?.length > 0 && (
        <div className="card">
          <div className="label mb-1">Similar past incidents</div>
          {inc.similar.map((s) => (
            <p key={s.incident} className="text-sm"><span className="font-mono">{s.incident}</span> {s.score.toFixed(2)}
              {s.score >= 0.6 && <span className="ml-1 rounded bg-emerald-800 px-1 text-xs">strong match</span>}
              <span className="block text-xs text-slate-400">fixed by {s.fixes.join(", ") || "-"}</span></p>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <div className="label">Proposed actions</div>
        {inc.actions.filter((a) => a.status !== "rejected").map((a) => <ActionCard key={a.id} a={a} onChanged={onChanged} />)}
        {inc.actions.length === 0 && <p className="text-sm text-slate-400">waiting for the agent…</p>}
      </div>
    </div>
  );
}
