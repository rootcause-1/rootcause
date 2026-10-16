// The incident dossier: one continuous sheet, read top to bottom like an on-call engineer would —
// verdict and evidence chain, ranked causes (the five weighted graph signals), what changed, who is hurt,
// have we seen this before, what to do (action cards), and the agent's investigation steps.
import { useEffect, useState } from "react";
import type { Hypothesis, Incident } from "../api";
import { api, clock, pct } from "../api";
import ActionCard from "./ActionCard";
import { inline } from "./Inline";
import TrailDrawer from "./TrailDrawer";

const WEIGHTS: Record<string, number> = { depth: 0.3, self: 0.25, pagerank: 0.2, change: 0.15, memory: 0.1 };
const SIGNAL: Record<string, { colour: string; name: string }> = {
  depth: { colour: "bg-pine", name: "nothing left to blame" },
  self: { colour: "bg-raspberry", name: "fails on its own" },
  pagerank: { colour: "bg-plum", name: "blame flows to it" },
  change: { colour: "bg-saffron", name: "changed just before" },
  memory: { colour: "bg-eucalyptus", name: "seen before" },
};

function Cause({ h, top }: { h: Hypothesis; top: boolean }) {
  return (
    <li className="py-1.5">
      <div className="flex items-baseline justify-between">
        <span className={top ? "font-display text-xl font-bold text-raspberry" : "text-[15px] font-medium"}>
          {h.target.replace(/^edge:/, "")}
          {h.target.startsWith("edge:") && <span className="ml-1 text-xs font-normal text-pine-soft">(the connection)</span>}
        </span>
        <span className={top ? "font-display text-xl font-bold" : "text-sm text-pine-soft"}>{h.score.toFixed(2)}</span>
      </div>
      <div className="mt-1 flex h-2 w-full overflow-hidden rounded-full bg-mist/60">
        {Object.keys(WEIGHTS).map((s) => (
          <div key={s} title={`${SIGNAL[s].name}: ${(h[s as keyof Hypothesis] as number).toFixed(2)}`}
               className={SIGNAL[s].colour} style={{ width: `${(h[s as keyof Hypothesis] as number) * WEIGHTS[s] * 100}%` }} />
        ))}
      </div>
    </li>
  );
}

type Change = Incident["changes"][number];

/** Identical changes in a row (a container that keeps dying) become one line with a count and the latest time. */
export function groupChanges(changes: Change[]): (Change & { count: number })[] {
  const out: (Change & { count: number })[] = [];
  for (const c of changes) {
    const same = out.find((o) => o.target === c.target && o.kind === c.kind && o.from_variant === c.from_variant && o.to === c.to);
    if (same) { same.count += 1; if (c.ts > same.ts) same.ts = c.ts; } else out.push({ ...c, count: 1 });
  }
  return out;
}

type Blast = { upstream: string[]; journeys: string[] } | null;

export default function IncidentPanel({ inc, onChanged, onCite, onBlast }: {
  inc: Incident; onChanged: () => void; onCite: (ids: string[]) => void; onBlast: (ids: string[]) => void;
}) {
  const firing = inc.alerts.filter((a) => a.status === "firing").length;
  const open = inc.status === "open";
  const actions = inc.actions.filter((a) => a.status !== "rejected");
  const root = inc.root_target ? inc.root_target.replace(/^edge:.*->/, "") : null;
  const [blast, setBlast] = useState<Blast>(null);
  useEffect(() => { setBlast(null); onBlast([]); }, [inc.id, root]); // eslint-disable-line react-hooks/exhaustive-deps
  async function toggleBlast() {
    if (blast || !root) { setBlast(null); onBlast([]); return; }
    const b = await api.blast(root).catch(() => null);
    if (!b) return;
    const ids = b.upstream.filter((id) => id !== root);
    setBlast({ upstream: ids, journeys: b.journeys });
    onBlast(ids);
  }
  return (
    <div className="space-y-6">
      <header>
        <div className="flex items-center justify-between">
          <h2 className="font-display text-2xl font-bold tracking-tight">{inc.id}</h2>
          <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${open ? "bg-raspberry/10 text-raspberry" : "bg-eucalyptus/15 text-pine"}`}>
            {open ? (inc.agent_state === "awaiting_approval" ? "waiting for your approval" : inc.agent_state ?? "open") : "resolved"}
          </span>
        </div>
        <p className="mt-1 text-sm muted">
          Opened {clock(inc.created_ts)}. {firing} of {inc.alerts.length} alerts still firing.
          {inc.ttr_ms ? ` Resolved in ${Math.round(inc.ttr_ms / 1000)} s.` : ""}
        </p>
        {inc.verdict?.narrative && <p className="mt-3 text-[15px] leading-relaxed">{inline(inc.verdict.narrative)}</p>}
      </header>

      {inc.evidence_path?.length > 0 && (
        <section>
          <h3 className="section-title">Evidence path</h3>
          <ol className="flex flex-wrap items-center gap-1.5 text-sm">
            {inc.evidence_path.map((n, i) => (
              <li key={n} className="flex items-center gap-1.5">
                <span className={`rounded-full px-2.5 py-0.5 ${i === inc.evidence_path.length - 1 ? "bg-raspberry font-semibold text-paper" : "bg-saffron/15"}`}>{n}</span>
                {i < inc.evidence_path.length - 1 && <span aria-hidden className="text-pine-soft">⟶</span>}
              </li>
            ))}
          </ol>
          {root && !root.includes(":") && (
            <div className="mt-2 text-sm">
              <button className="btn-ghost py-1 text-xs" onClick={toggleBlast} aria-pressed={!!blast}>
                <i className="inline-block h-2 w-2 rounded-full bg-lake" />{blast ? "Hide blast radius" : "Show blast radius"}
              </button>
              {blast && (
                <p className="mt-1.5 muted">
                  {blast.upstream.length === 0 ? `Nothing calls ${root}.` : `${blast.upstream.length} services depend on ${root}: ${blast.upstream.join(", ")}.`}
                  {blast.journeys.length > 0 && ` Journeys: ${blast.journeys.map((j) => j.replace("journey:", "")).join(", ")}.`}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      <section>
        <h3 className="section-title">Ranked causes</h3>
        <ol>{inc.hypotheses.slice(0, 4).map((h, i) => <Cause key={h.target} h={h} top={i === 0} />)}</ol>
        {inc.hypotheses.length === 0 && <p className="text-sm muted">Ranking…</p>}
        <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs muted">
          {Object.keys(WEIGHTS).map((s) => (
            <li key={s} className="flex items-center gap-1.5"><i className={`inline-block h-2 w-2 rounded-full ${SIGNAL[s].colour}`} />{SIGNAL[s].name}</li>
          ))}
        </ul>
      </section>

      <section className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div>
          <h3 className="section-title">What changed</h3>
          {inc.changes.length === 0 && <p className="text-sm muted">Nothing near the onset.</p>}
          {groupChanges(inc.changes).map((c) => (
            <p key={c.id} className="mb-1 text-sm"><b>{c.target}</b> {c.from_variant ?? ""} → {c.to ?? c.kind}
              {c.count > 1 && <span className="ml-1 rounded-full bg-mist/70 px-1.5 text-xs">×{c.count}</span>}
              <span className="block text-xs muted">{c.count > 1 ? "last at " : ""}{clock(c.ts)}, by {c.actor}</span></p>
          ))}
        </div>
        <div>
          <h3 className="section-title">Who is hurt</h3>
          {inc.impact.length === 0 && <p className="text-sm muted">No journey has dropped.</p>}
          {inc.impact.map((i) => (
            <div key={i.journey} className="mb-1.5 text-sm">
              <div className="flex justify-between"><span>{i.journey.replace("journey:", "")} journey</span><b className="text-raspberry">−{pct(i.pct)}</b></div>
              <div className="mt-0.5 h-1.5 rounded-full bg-mist/60"><div className="h-1.5 rounded-full bg-raspberry" style={{ width: pct(i.pct) }} /></div>
            </div>
          ))}
        </div>
      </section>

      {inc.similar?.length > 0 && (
        <section>
          <h3 className="section-title">Seen before</h3>
          {inc.similar.slice(0, 3).map((s) => (
            <p key={s.incident} className="text-sm">
              <b>{s.incident}</b>, {Math.round(s.score * 100)} % similar{s.score >= 0.6 ? ", a strong match" : ""}
              {s.fixes.length > 0 && <span className="block text-xs muted">fixed by {s.fixes.join(", ")}</span>}
            </p>
          ))}
        </section>
      )}

      <section>
        <h3 className="section-title">What to do</h3>
        <div className="space-y-2">
          {actions.map((a) => <ActionCard key={a.id} a={a} onChanged={onChanged} closed={!open} />)}
        </div>
        {actions.length === 0 && <p className="text-sm muted">The agent is still investigating.</p>}
      </section>

      <section>
        <h3 className="section-title">How the agent got there</h3>
        <TrailDrawer steps={inc.steps} onHover={onCite} />
      </section>
    </div>
  );
}
