// The narrator: one popup over the map that tells the incident as it really unfolds, and moves on by itself.
//
// Each step is unlocked by real state (graph snapshot, Incident / Action nodes), and stays on screen for a minimum time
// so a viewer can read it before the next one appears. Nothing is scripted: if the system has not reached a step yet,
// the narrator waits for it.
//
// The fix: "Should I fix this?" is a real approval (POST /api/actions/{id}/approve mints the single-use token and
// executes). In the replay demo with autoplay on, a visible countdown clicks "Yes" for the viewer, only for low-risk
// fixes; in live mode the narrator always waits for a person.
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Action, Graph, Hypothesis, Incident, Status } from "../api";
import { api, pct } from "../api";
import ActionCard from "./ActionCard";
import { journeyState, nameOf, perHour } from "./ServiceMap";

export const STAGES = ["intro", "healthy", "alerts", "grouped", "investigating", "root", "impact", "fix", "fixing", "recovered"] as const;
export type Stage = (typeof STAGES)[number];
export const STAGE_LABEL: Record<Stage, string> = {
  intro: "Welcome", healthy: "Healthy", alerts: "Alerts", grouped: "One incident", investigating: "Investigating",
  root: "Root cause", impact: "Impact", fix: "Fix", fixing: "Fixing", recovered: "Recovered",
};
const DWELL: Partial<Record<Stage, number>> = { healthy: 9000, alerts: 8000, grouped: 8000, investigating: 6000, root: 12000, impact: 11000 };
const AUTO_APPROVE_S = 12;
const KIND: Record<string, string> = {
  error_rate: "errors", latency: "slow responses", lag: "a growing backlog", memory: "memory growing",
  cpu: "CPU saturated", agent_loop: "an AI agent looping", llm_latency: "slow AI answers", gc: "garbage-collection pressure",
};

export function describe(a: Action): string {
  if (a.kind === "flag_revert") return `Switch feature flag "${a.target}" back to "${String(a.params?.variant ?? "off")}"`;
  if (a.kind === "restart") return `Restart ${nameOf(a.target)}`;
  if (a.kind === "page") return `Page the ${a.target}`;
  return `${a.kind.replace(/_/g, " ")} ${a.target}`;
}

/** Plain-English reasons, read off the top hypothesis' five signal scores and the change linked to the incident. */
function reasons(h: Hypothesis, inc: Incident): string[] {
  const id = h.target.replace(/^edge:/, "");
  const root = h.target.startsWith("edge:") ? id : nameOf(id);
  const out: string[] = [];
  if (h.target.startsWith("edge:")) {
    const [a, b] = id.split("->");
    out.push(`${nameOf(a)} keeps calling ${nameOf(b)}, but nothing answers: the connection is broken, not the code.`);
  }
  if (h.self >= 0.5) out.push(`The failures start inside ${root} itself.`);
  if (h.depth >= 0.99) out.push(`Nothing ${root} depends on is failing, so the trail of blame stops here.`);
  if (h.pagerank >= 0.5) out.push(`Following "who fails because of whom" through the graph, the blame flows to ${root}.`);
  const ch = inc.changes[0];
  if (h.change > 0 && ch) {
    const mins = Math.max(0, Math.round((inc.onset_ts - ch.ts) / 60000));
    out.push(ch.kind === "flag"
      ? `Feature flag "${ch.target}" was switched from "${ch.from_variant ?? "?"}" to "${ch.to}" ${mins ? `${mins} min` : "moments"} before the alerts.`
      : `${ch.target} had a ${ch.kind} ${mins ? `${mins} min` : "moments"} before the alerts.`);
  }
  if (h.memory > 0) out.push(`It looks like a past incident (${pct(h.memory)} alike).`);
  return out;
}

const APPLIED = new Set(["approved", "executing", "executed", "verified", "failed"]);

export function targetStage(status: Status | null, inc: Incident | null, demo: boolean): Stage {
  if (!inc || (inc.status === "resolved" && Date.now() - (inc.resolved_ts ?? 0) > 5 * 60_000)) {
    return demo || status?.mode !== "replay" ? "healthy" : "intro";
  }
  if (inc.status === "resolved") return "recovered";
  const applied = inc.actions.some((a) => APPLIED.has(a.status) && a.kind !== "page" && a.status !== "failed");
  if (applied) return "fixing";
  const top = inc.hypotheses[0];
  if (!top || inc.agent_state === "pending" || inc.agent_state === "investigating") return "investigating";
  if (inc.actions.some((a) => a.status === "proposed")) return "fix";
  return "impact";
}

/** Shown stage walks towards the target one step at a time, waiting each step's dwell time. */
export function useNarration(target: Stage): Stage {
  const [shown, setShown] = useState<Stage>(target);
  const since = useRef(Date.now());
  useEffect(() => {
    const ti = STAGES.indexOf(target), si = STAGES.indexOf(shown);
    if (ti < si || shown === "intro" || target === "intro") { setShown(target); since.current = Date.now(); return; }
    if (ti === si) return;
    // far behind (e.g. the page was opened mid-incident): recap the earlier steps quickly
    const dwell = ti - si > 2 ? 2500 : DWELL[shown] ?? 0;
    const wait = Math.max(0, dwell - (Date.now() - since.current));
    const t = setTimeout(() => { setShown(STAGES[si + 1]); since.current = Date.now(); }, wait);
    return () => clearTimeout(t);
  }, [target, shown]);
  return shown;
}

function Tick({ done, active, failed, children, note }: { done?: boolean; active?: boolean; failed?: boolean; children: ReactNode; note?: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 shrink-0">
        {done ? <span className="grid h-5 w-5 place-items-center rounded-full bg-eucalyptus text-[11px] font-bold text-white">✓</span>
          : failed ? <span className="grid h-5 w-5 place-items-center rounded-full bg-raspberry text-[11px] text-white">✕</span>
          : active ? <span className="block h-5 w-5 animate-spin rounded-full border-2 border-saffron border-t-transparent" />
          : <span className="block h-5 w-5 rounded-full border-2 border-mist" />}
      </span>
      <div className={!done && !active && !failed ? "muted" : ""}><div>{children}</div>{note && <div className="text-xs muted">{note}</div>}</div>
    </li>
  );
}

export default function Narrator({ stage, status, inc, graph, demo, autoplay, onStart, onAutoplay, onChanged, onCite, onBlast, onOpenReport }: {
  stage: Stage; status: Status | null; inc: Incident | null; graph: Graph | null; demo: boolean; autoplay: boolean;
  onStart: () => void; onAutoplay: (on: boolean) => void; onChanged: () => void;
  onCite: (ids: string[]) => void; onBlast: (ids: string[]) => void; onOpenReport: () => void;
}) {
  const replay = status?.mode === "replay";
  const alerts = inc?.alerts ?? [];
  const alerting = [...new Set(alerts.map((a) => a.target))];
  const owners = (ids: string[]) => (graph?.teams ?? []).filter((t) => t.owns.some((s) => ids.includes(s)));
  const top = inc?.hypotheses[0];
  const proposed = (inc?.actions ?? []).filter((a) => a.status === "proposed");
  const fix = proposed.find((a) => a.kind !== "page") ?? proposed[0];
  const applied = [...(inc?.actions ?? [])].reverse().find((a) => APPLIED.has(a.status) && a.kind !== "page");

  // the blue "touched by the fix" rings while the fix is being proposed
  useEffect(() => { onBlast(stage === "fix" && fix ? fix.side_effects?.affected_services ?? [] : []); }, [stage, fix?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // autoplay countdown for the demo approval (replay only, never for high-risk fixes)
  const canAuto = replay && demo && autoplay && stage === "fix" && !!fix && fix.risk !== "high" && fix.kind !== "page";
  const [left, setLeft] = useState(AUTO_APPROVE_S);
  const [busy, setBusy] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setLeft(AUTO_APPROVE_S); setDeclined(false); setErr(null); }, [fix?.id]);
  useEffect(() => {
    if (!canAuto || declined || busy) return;
    if (left <= 0) { approve(); return; }
    const t = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [canAuto, declined, busy, left]); // eslint-disable-line react-hooks/exhaustive-deps

  async function approve() {
    if (!fix) return;
    setBusy(true); setErr(null);
    try { await api.approve(fix.id); onChanged(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  let kicker = STAGE_LABEL[stage];
  let title: ReactNode = null;
  let body: ReactNode = null;

  if (stage === "intro") {
    kicker = "RootCause";
    title = <>Root<span className="italic">Cause</span>, the AI on-call engineer</>;
    body = (
      <>
        <p>When something breaks in a company's systems, dozens of alarms go off at once and engineers lose precious minutes
          finding the one real cause. RootCause finds it for them, explains why, and fixes it with their approval.</p>
        <ul className="mt-3 space-y-1.5 text-[15px]">
          <li><b>Left:</b> the shop's customers and what they are doing.</li>
          <li><b>Middle:</b> every service the company runs, grouped by the team that owns it.</li>
          <li><b>Moving dots:</b> real requests, live. Red dots are failing requests.</li>
        </ul>
        <button className="btn-primary mt-5 px-5 py-2 text-base" onClick={onStart}>▶ Start the demo</button>
        <p className="mt-2 text-xs muted">About 3 minutes. Replays telemetry recorded from the real OpenTelemetry Demo through the real engine.</p>
      </>
    );
  } else if (stage === "healthy") {
    title = "Everything is running normally";
    body = (
      <p>{graph?.nodes.filter((n) => n.labels.includes("Service")).length ?? 0} services are serving customers. RootCause turns every request
        into nodes and edges in a FalkorDB graph and learns what normal looks like.
        {demo && replay ? " In this recording, something is about to break. Watch the map." : " If anything breaks, the story starts here."}</p>
    );
  } else if (stage === "alerts" && inc) {
    const teams = owners(alerting);
    title = `${alerts.length} alarms just went off`;
    body = (
      <>
        <p>{alerting.map(nameOf).join(", ")} are reporting {[...new Set(alerts.map((a) => KIND[a.kind] ?? a.kind))].join(" and ")}.</p>
        <p className="mt-2">Without RootCause, {teams.length || "several"} team{teams.length === 1 ? "" : "s"} would be woken up
          {teams.length ? ` (${teams.map((t) => t.name).join(", ")})` : ""}, each looking at their own red dashboard.</p>
      </>
    );
  } else if (stage === "grouped" && inc) {
    title = `${alerts.length} alarms, 1 incident`;
    body = <p>RootCause followed the calls between these services in the graph and saw they are failing because of one
      another, so it opened <b>one incident</b> instead of {alerts.length} separate pages.</p>;
  } else if (stage === "investigating" && inc) {
    title = "The AI agent is investigating";
    body = (
      <>
        <p>It queries the graph through its tools, step by step. Hover a step to see what it looked at.</p>
        <ol className="mt-3 space-y-1.5">
          {inc.steps.slice(-6).map((s) => (
            <li key={s.id} className="grid grid-cols-[64px_1fr] gap-2 rounded-lg px-2 py-1 text-sm hover:bg-mist/40"
                onMouseEnter={() => onCite(s.cited)} onMouseLeave={() => onCite([])}>
              <span className="font-mono text-[11px] uppercase tracking-wider text-eucalyptus">agent<br /><span className="muted">{new Date(s.ts).toLocaleTimeString([], { hour12: false })}</span></span>
              <span><span className="rounded bg-mist/60 px-1.5 py-0.5 font-mono text-[11px]">{s.tool}</span> <span className="muted">{s.summary}</span></span>
            </li>
          ))}
          {inc.steps.length === 0 && <li className="text-sm muted">Starting…</li>}
        </ol>
      </>
    );
  } else if (stage === "root" && inc && top) {
    const name = top.target.startsWith("edge:") ? top.target.slice(5).split("->").map(nameOf).join(" → ") : nameOf(top.target);
    title = <>Root cause: <span className="text-raspberry">{name}</span></>;
    body = (
      <>
        <p className="font-mono text-xs muted">ranked 1 of {inc.hypotheses.length} suspects · confidence {top.score.toFixed(2)}</p>
        <ol className="mt-3 divide-y divide-mist border-y border-mist">
          {reasons(top, inc).map((r, i) => (
            <li key={r} className="grid grid-cols-[28px_1fr] gap-2 py-2"><span className="font-mono text-xs muted">{String(i + 1).padStart(2, "0")}</span>{r}</li>
          ))}
        </ol>
        {inc.evidence_path.length > 1 && (
          <p className="mt-3 text-sm"><span className="kicker mr-2">evidence trail</span>{inc.evidence_path.map(nameOf).join(" → ")}</p>
        )}
      </>
    );
  } else if (stage === "impact" && inc) {
    const ids = [...new Set([...alerting, ...(top ? [top.target.replace(/^edge:.*->/, "")] : [])])];
    const teams = owners(ids);
    const rootId = top?.target.replace(/^edge:.*->/, "") ?? null;
    const hurt = (graph?.journeys ?? []).filter((j) => journeyState(j, rootId) !== "ok" && (j.rps ?? 0) > 0);
    title = "One fault, felt across the company";
    body = (
      <>
        <div className="mt-1 grid grid-cols-4 gap-2 text-center">
          {[["1", "root cause"], [String(alerting.length), "services alerting"], [String(teams.length), "teams affected"], [String(hurt.length), "customer journeys hurt"]].map(([v, l], i) => (
            <div key={l} className="rounded-xl border border-mist bg-white px-1 py-2">
              <div className={`font-display text-4xl leading-none ${i === 0 || i === 3 ? "text-raspberry" : "text-saffron"}`}>{v}</div>
              <div className="text-[11px] leading-tight muted">{l}</div>
            </div>
          ))}
        </div>
        <ul className="mt-3 space-y-1.5">
          {hurt.map((j) => (
            <li key={j.id}>Customers trying to <b>{j.name.toLowerCase()}</b>: {journeyState(j, rootId) === "hurt"
              ? `${Math.round((1 - (j.success_rate ?? 1)) * 100)} % failing` : "at risk"}
              <span className="muted"> (about {perHour(j.rps)} attempts an hour)</span></li>
          ))}
          {hurt.length === 0 && <li className="muted">No customer journey has dropped measurably yet.</li>}
        </ul>
      </>
    );
  } else if (stage === "fix" && inc && fix) {
    const se = fix.side_effects ?? {};
    title = "Should I fix this?";
    body = (
      <>
        <div className="rounded-xl border border-mist bg-white p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="font-semibold">{describe(fix)}</p>
            <span className={`shrink-0 rounded-full px-2 py-0.5 font-mono text-[11px] ${fix.risk === "high" ? "bg-raspberry/15 text-raspberry" : "bg-eucalyptus/10 text-eucalyptus"}`}>{fix.risk} risk</span>
          </div>
          <ul className="mt-2 space-y-1 text-sm muted">
            <li>Why: {fix.reason}</li>
            <li>Touches: {se.affected_services?.length ? se.affected_services.map(nameOf).join(", ") : "nothing else"} (blue rings on the map)</li>
            <li>Success check: all {alerts.length} alarms clear and stay clear. If not, I stop and suggest the next option.</li>
          </ul>
        </div>
        {fix.risk === "high" ? (
          <div className="mt-3"><p className="mb-2 text-sm">This one is high risk, so it needs a typed confirmation.</p>
            <ActionCard a={fix} onChanged={onChanged} /></div>
        ) : (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button className="btn-primary" disabled={busy} onClick={approve}>{busy ? "Applying…" : "Yes, fix it"}</button>
            <button className="btn-ghost" disabled={busy} onClick={() => { setDeclined(true); onAutoplay(false); }}>Not now</button>
          </div>
        )}
        {canAuto && !declined && (
          <div className="mt-3">
            <div className="h-1 overflow-hidden rounded-full bg-mist">
              <div className="h-1 rounded-full bg-plum transition-all duration-1000 ease-linear" style={{ width: `${(left / AUTO_APPROVE_S) * 100}%` }} />
            </div>
            <p className="mt-1.5 text-xs muted">Demo autoplay: saying yes for you in {left} s. In real use a person approves every change.
              <button className="ml-1 underline" onClick={() => onAutoplay(false)}>Let me decide</button></p>
          </div>
        )}
        {declined && <p className="mt-2 text-sm muted">Okay, nothing changes. The alarms keep firing until someone approves a fix.</p>}
        {proposed.length > 1 && (
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer muted">Other options ({proposed.length - 1})</summary>
            <div className="mt-2 space-y-2">{proposed.filter((a) => a.id !== fix.id).map((a) => <ActionCard key={a.id} a={a} onChanged={onChanged} />)}</div>
          </details>
        )}
        {err && <p className="mt-2 text-sm text-raspberry">{err}</p>}
      </>
    );
  } else if (stage === "fixing" && inc && applied) {
    const s = applied.status;
    const ran = s === "executed" || s === "verified" || s === "failed";
    const ok = s === "verified";
    const cleared = alerts.filter((a) => a.status === "resolved").length;
    title = ok ? "Fixed and verified" : "Fixing it now";
    body = (
      <ol className="space-y-2.5">
        <Tick done>Approved: {describe(applied)}</Tick>
        <Tick done={ran} active={!ran} note={replay && ran ? "Simulated in this replay; the recovery you see was recorded on the real demo." : undefined}>
          {ran ? "Change applied" : "Applying the change…"}</Tick>
        <Tick done={ok} active={ran && !ok && s !== "failed"} failed={s === "failed"}
              note={ran && !ok && s !== "failed" ? "An alarm clears after 3 healthy checks in a row. Watch the red dots disappear." : undefined}>
          {ok ? "Every alarm has cleared" : `Watching recovery: ${cleared} of ${alerts.length} alarms cleared`}</Tick>
        <Tick done={ok}>Verified: the incident is resolved</Tick>
      </ol>
    );
  } else if (stage === "recovered" && inc) {
    const fixAt = inc.actions.find((a) => a.executed_ts)?.executed_ts;
    const after = fixAt && inc.resolved_ts ? Math.round((inc.resolved_ts - fixAt) / 1000) : null;
    title = "Back to normal";
    body = (
      <>
        <p>{after != null ? `The shop recovered ${after} seconds after the fix. ` : "The shop recovered. "}
          All {alerts.length} alarms have cleared, customers are getting through again, and the post-incident report is written.
          RootCause remembers this incident, so next time it offers the same fix first.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn-primary" onClick={onOpenReport}>Read the report</button>
          {replay && <button className="btn-ghost" onClick={onStart}>▶ Run the demo again</button>}
        </div>
      </>
    );
  } else {
    title = "Working…";
  }

  const idx = STAGES.indexOf(stage);
  const busyNow = stage === "investigating" || stage === "fixing";
  const strip: Partial<Record<Stage, string>> = {
    intro: "Ready when you are", healthy: "Watching every request", alerts: "Alarms firing", grouped: "Grouping the alarms",
    investigating: "Investigating", root: "Found the root cause", impact: "Measuring the impact", fix: "Waiting for your approval",
    fixing: "Applying the fix", recovered: "All clear",
  };
  return (
    <div className="sheet w-full overflow-hidden text-[15px] leading-relaxed" role="status" aria-live="polite">
      <div className={`flex items-center gap-3 px-5 py-3 text-white ${stage === "alerts" || stage === "grouped" ? "bg-[#8E3B2E]" : "bg-eucalyptus"}`}>
        <span className="grid h-7 w-7 place-items-center rounded-full bg-white/15">
          <span className={`h-2.5 w-2.5 rounded-full bg-white ${busyNow || stage === "fix" ? "animate-pulse" : ""}`} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">RootCause · {strip[stage]}</p>
          <p className="font-mono text-[11px] text-white/70">{stage === "intro" ? "replay of the OpenTelemetry Demo" : `step ${idx} of ${STAGES.length - 1}${inc ? ` · ${inc.id}` : ""}`}</p>
        </div>
        {replay && demo && stage !== "intro" && (
          <button className="rounded-md bg-white/15 px-2 py-1 font-mono text-[11px] hover:bg-white/25" onClick={() => onAutoplay(!autoplay)}>
            {autoplay ? "autoplay on" : "autoplay off"}</button>
        )}
      </div>
      <div className="p-5">
        <p className="kicker">{kicker}</p>
        <h2 className="mt-1 font-display text-[32px] leading-[1.1]">{title}</h2>
        <div className="mt-3">{body}</div>
      </div>
    </div>
  );
}
