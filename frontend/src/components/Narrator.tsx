// The narrator: the incident told as a WhatsApp-style chat between RootCause and the on-call engineer, on a phone
// next to the map. It moves on by itself.
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
import { api, codeLink, pct } from "../api";
import ActionCard from "./ActionCard";
import { journeyState, nameOf, perHour } from "./ServiceMap";

function ago(ts: number): string {
  const d = Math.round((Date.now() - ts) / 86_400_000);
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
}

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
  if (a.kind === "automation") return `Run your runbook automation "${String(a.params?.title ?? a.target)}"`;
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
  if (h.explains?.length) {
    const dbs = h.explains.map(nameOf).join(" and ");
    out.push(`${dbs} looks slow too, but a database cannot break on its own without a change or a resource alarm. It is slow because of ${root}.`);
  }
  if (h.depth >= 0.99 && !h.explains?.length) out.push(`Nothing ${root} depends on is failing, so the trail of blame stops here.`);
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

function Tick({ done, active, failed, children }: { done?: boolean; active?: boolean; failed?: boolean; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span className="mt-[3px] shrink-0">
        {done ? <span className="grid h-4 w-4 place-items-center rounded-full bg-eucalyptus text-[9px] font-bold text-white">✓</span>
          : failed ? <span className="grid h-4 w-4 place-items-center rounded-full bg-raspberry text-[9px] text-white">✕</span>
          : active ? <span className="block h-4 w-4 animate-spin rounded-full border-2 border-saffron border-t-transparent" />
          : <span className="block h-4 w-4 rounded-full border-2 border-mist" />}
      </span>
      <span className={!done && !active && !failed ? "muted" : ""}>{children}</span>
    </li>
  );
}

const hhmm = (ms?: number) => (ms ? new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) : "");

/** One chat bubble. RootCause on the left (white), the on-call engineer on the right (green, read ticks). */
function Bubble({ me, time, children }: { me?: boolean; time?: number; children: ReactNode }) {
  return (
    <div className={`flex ${me ? "justify-end" : "justify-start"} animate-[popup_.35s_ease-out]`}>
      <div className={`relative max-w-[88%] rounded-xl px-3 pb-1.5 pt-2 text-[14px] leading-snug shadow-[0_1px_0.5px_rgba(0,0,0,0.13)] ${
        me ? "rounded-tr-none bg-[#D9FDD3]" : "rounded-tl-none bg-white"}`}>
        {children}
        <div className="mt-1 flex items-center justify-end gap-1 font-mono text-[10px] text-[#667781]">
          {hhmm(time)}{me && <span className="text-[#53BDEB]">✓✓</span>}
        </div>
      </div>
    </div>
  );
}

/** The welcome card, shown over the map before the demo starts. */
export function Intro({ onStart }: { onStart: () => void }) {
  return (
    <div className="sheet w-full overflow-hidden text-[15px] leading-relaxed">
      <div className="p-6">
        <p className="kicker">RootCause</p>
        <h2 className="mt-1 font-display text-[34px] leading-[1.1]">The AI on-call engineer that finds the <i>one</i> real cause</h2>
        <p className="mt-3">When something breaks in a company's systems, dozens of alarms go off at once and engineers lose precious
          minutes finding the one real cause. RootCause finds it, explains why in plain words, and fixes it once you say yes,
          over a chat like this one.</p>
        <ul className="mt-3 space-y-1 text-[15px]">
          <li><b>Left of the map:</b> the shop's customers and what they are doing.</li>
          <li><b>Middle:</b> every service the company runs, grouped by the team that owns it.</li>
          <li><b>Moving dots:</b> real requests. Red dots are failing requests.</li>
        </ul>
        <button className="btn-primary mt-5 px-5 py-2 text-base" onClick={onStart}>▶ Start the demo</button>
        <p className="mt-2 text-xs muted">About 3 minutes. Replays telemetry recorded from the real OpenTelemetry Demo through the real engine.</p>
      </div>
    </div>
  );
}

/** The incident as a WhatsApp-style conversation between RootCause and the on-call engineer. */
export default function Narrator({ stage, typing, status, inc, graph, demo, autoplay, onStart, onAutoplay, onChanged, onCite, onBlast, onOpenReport }: {
  stage: Stage; typing: boolean; status: Status | null; inc: Incident | null; graph: Graph | null; demo: boolean; autoplay: boolean;
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
  const inFlight = !!applied && applied.status !== "failed"; // a fix is being applied or verified: don't ask again
  const si = STAGES.indexOf(stage);
  const at = (s: Stage) => si >= STAGES.indexOf(s);

  // when each message first appeared (its timestamp in the chat)
  const seen = useRef<Partial<Record<Stage, number>>>({});
  if (!seen.current[stage]) seen.current[stage] = Date.now();
  useEffect(() => { if (stage === "healthy" && !inc) seen.current = { healthy: Date.now() }; }, [stage, inc]);
  const t = (s: Stage) => seen.current[s];

  // the lilac "touched by the fix" rings while the fix is being proposed
  useEffect(() => { onBlast(stage === "fix" && fix ? fix.side_effects?.affected_services ?? [] : []); }, [stage, fix?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // autoplay countdown for the demo approval (replay only, never for high-risk fixes)
  const canAuto = replay && demo && autoplay && stage === "fix" && !!fix && fix.risk !== "high" && fix.kind !== "page" && !inFlight;
  const [left, setLeft] = useState(AUTO_APPROVE_S);
  const [busy, setBusy] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [said, setSaid] = useState<number | null>(null); // when "Yes, fix it" was sent
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setLeft(AUTO_APPROVE_S); setDeclined(false); setErr(null); if (!inFlight) setSaid(null); }, [fix?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!canAuto || declined || busy || said) return;
    if (left <= 0) { approve(); return; }
    const timer = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [canAuto, declined, busy, left]); // eslint-disable-line react-hooks/exhaustive-deps

  async function approve() {
    if (!fix || said || inFlight) return; // one approval per proposal
    setBusy(true); setErr(null); setSaid(Date.now());
    try { await api.approve(fix.id); onChanged(); } catch (e) { setErr((e as Error).message); setSaid(null); } finally { setBusy(false); }
  }

  // keep the newest message in view (after the bubble has rendered and animated in)
  const body = useRef<HTMLDivElement>(null);
  const scrollKey = `${si}|${typing}|${inc?.steps.length}|${applied?.status}|${said}|${declined}|${inc?.alerts.filter((a) => a.status === "resolved").length}`;
  useEffect(() => {
    const go = () => body.current?.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" });
    go();
    const timer = setTimeout(go, 400);
    return () => clearTimeout(timer);
  }, [scrollKey]);

  const services = graph?.nodes.filter((n) => n.labels.includes("Service")).length ?? 0;
  const msgs: ReactNode[] = [];

  if (at("healthy")) msgs.push(
    <Bubble key="hi" time={t("healthy")}>👋 Hi, I'm <b>RootCause</b>, your on-call agent. I'm watching all {services} services of the shop
      as a live graph. Everything is normal right now.{demo && replay ? " (In this recording, something is about to break.)" : ""}</Bubble>);

  if (at("alerts") && inc) {
    const teams = owners(alerting);
    msgs.push(
      <Bubble key="alerts" time={alerts[0]?.ts ?? t("alerts")}>🚨 <b>{alerts.length} alarms just went off</b>: {alerting.map(nameOf).join(", ")}
        {" "}({[...new Set(alerts.map((a) => KIND[a.kind] ?? a.kind))].join(", ")}).
        {teams.length > 0 && <> Normally that pages {teams.length} team{teams.length === 1 ? "" : "s"} ({teams.map((x) => x.name).join(", ")}).</>}</Bubble>);
  }
  if (at("grouped") && inc) msgs.push(
    <Bubble key="grouped" time={inc.created_ts}>They're one problem, not {alerts.length}. These services fail <i>because of each other</i>
      {" "}(I can see it in the call graph), so I opened <b>one incident</b>: <span className="font-mono text-[12px]">{inc.id}</span>. Looking into it 🔎</Bubble>);

  if (at("investigating") && inc) msgs.push(
    <Bubble key="steps" time={t("investigating")}>
      <p className="mb-1 font-medium">What I'm checking in the graph:</p>
      <ol className="space-y-0.5">
        {inc.steps.slice(0, 9).map((s) => (
          <li key={s.id} className="cursor-default rounded px-1 text-[12.5px] hover:bg-mist/50"
              onMouseEnter={() => onCite(s.cited)} onMouseLeave={() => onCite([])}>
            <span className="text-eucalyptus">✓</span> <span className="font-mono text-[11.5px]">{s.tool}</span> <span className="muted">{s.summary}</span>
          </li>
        ))}
        {inc.steps.length === 0 && <li className="muted">starting…</li>}
      </ol>
    </Bubble>);

  if (at("root") && inc && top) {
    const name = top.target.startsWith("edge:") ? top.target.slice(5).split("->").map(nameOf).join(" → ") : nameOf(top.target);
    msgs.push(
      <Bubble key="root" time={t("root")}>
        <p>🎯 <b>Found it. The root cause is <span className="text-raspberry">{name}</span>.</b> <span className="muted">(confidence {top.score.toFixed(2)})</span></p>
        <ol className="mt-1.5 space-y-1">
          {reasons(top, inc).map((r, i) => <li key={r} className="grid grid-cols-[18px_1fr] text-[13.5px]"><span className="font-mono text-[11px] muted">{i + 1}.</span>{r}</li>)}
        </ol>
        {inc.evidence_path.length > 1 && <p className="mt-1.5 text-[12.5px] muted">Trail on the map: {inc.evidence_path.map(nameOf).join(" → ")}</p>}
      </Bubble>);
    const code = inc.code;
    if (code?.module && code.files) msgs.push(
      <Bubble key="code" time={t("root")}>
        <p>📂 <b>The code behind it:</b> <span className="font-mono text-[12.5px]">{code.path}</span>{" "}
          <span className="muted">({code.language}, {code.files} files, {code.loc?.toLocaleString()} lines{code.repo ? ` in ${code.repo.replace("https://github.com/", "")}` : ""})</span></p>
        {(code.reads ?? []).slice(0, 2).map((r) => (
          <p key={r.file + r.flag} className="mt-1 text-[13.5px]">Flag <b>{r.flag}</b> is read at{" "}
            {code.repo ? <a className="font-mono text-[12.5px] text-[#027EB5] underline" href={codeLink(code.repo, code.sha, r.file, r.line)} target="_blank" rel="noreferrer">{r.file}:{r.line}</a>
              : <span className="font-mono text-[12.5px]">{r.file}:{r.line}</span>}</p>
        ))}
        {code.commits?.[0] && <p className="mt-1 text-[12.5px] muted">Last change to this code: "{code.commits[0].subject}" ({ago(code.commits[0].ts)}).</p>}
        <p className="mt-1 text-[11.5px] muted">From your connected GitHub repo. It shows where to look; it doesn't change the diagnosis.</p>
      </Bubble>);
  }

  if (at("impact") && inc) {
    const ids = [...new Set([...alerting, ...(top ? [top.target.replace(/^edge:.*->/, "")] : [])])];
    const teams = owners(ids);
    const rootId = top?.target.replace(/^edge:.*->/, "") ?? null;
    const hurt = (graph?.journeys ?? []).filter((j) => journeyState(j, rootId) !== "ok" && (j.rps ?? 0) > 0);
    msgs.push(
      <Bubble key="impact" time={t("impact")}>
        <p>Who it hurts: <b>1 fault</b> → <b>{alerting.length} services</b> alerting → <b>{teams.length} teams</b> affected →</p>
        <ul className="mt-1 space-y-0.5">
          {hurt.map((j) => (
            <li key={j.id}>🛒 customers trying to <b>{j.name.toLowerCase()}</b>: <b className="text-raspberry">{journeyState(j, rootId) === "hurt"
              ? `${Math.round((1 - (j.success_rate ?? 1)) * 100)}% failing` : "at risk"}</b> <span className="muted">(~{perHour(j.rps)}/hour)</span></li>
          ))}
          {hurt.length === 0 && <li className="muted">no customer journey has dropped yet</li>}
        </ul>
      </Bubble>);
  }

  if (at("fix") && inc && (fix || applied)) {
    const a = inFlight || !fix ? applied! : fix; // the question stays the one that was answered
    const se = a.side_effects ?? {};
    msgs.push(
      <Bubble key="ask" time={t("fix")}>
        <p><b>Should I fix this?</b> 🛠️</p>
        <p className="mt-1">I'd <b>{describe(a).replace(/^./, (c) => c.toLowerCase())}</b>.</p>
        <p className="mt-1 text-[13px] muted">Risk: <b className={a.risk === "high" ? "text-raspberry" : "text-eucalyptus"}>{a.risk}</b> · touches
          {" "}{se.affected_services?.length ? se.affected_services.map(nameOf).join(", ") : "nothing else"} · I'll check all {alerts.length} alarms clear,
          and if they don't I stop and suggest the next option.</p>
      </Bubble>);
  }
  if ((said || applied) && inc) msgs.push(<Bubble key="yes" me time={said ?? applied?.executed_ts}>Yes, fix it 👍</Bubble>);
  if (declined && !applied) msgs.push(<Bubble key="no" me time={Date.now()}>Not now</Bubble>);
  if (declined && !applied) msgs.push(<Bubble key="ok" time={Date.now()}>Okay, I won't change anything. The alarms keep firing until someone says yes.</Bubble>);

  if (at("fixing") && inc && applied) {
    const s = applied.status;
    const ran = s === "executed" || s === "verified" || s === "failed";
    const ok = s === "verified" || inc.status === "resolved";
    const cleared = alerts.filter((x) => x.status === "resolved").length;
    msgs.push(
      <Bubble key="fixing" time={applied.executed_ts ?? t("fixing")}>
        <p className="mb-1 font-medium">On it:</p>
        <ul className="space-y-1 text-[13.5px]">
          <Tick done>approved by you</Tick>
          <Tick done={ran} active={!ran}>{ran ? "change applied" : "applying the change…"}{replay && ran ? <span className="muted"> (simulated in this replay)</span> : null}</Tick>
          <Tick done={ok} active={ran && !ok && s !== "failed"} failed={s === "failed"}>{ok ? "every alarm cleared" : `watching recovery: ${cleared} of ${alerts.length} alarms cleared`}</Tick>
          <Tick done={ok}>verified the incident is resolved</Tick>
        </ul>
      </Bubble>);
  }

  if (at("recovered") && inc) {
    const fixAt = inc.actions.find((x) => x.executed_ts)?.executed_ts;
    const after = fixAt && inc.resolved_ts ? Math.round((inc.resolved_ts - fixAt) / 1000) : null;
    msgs.push(
      <Bubble key="done" time={inc.resolved_ts}>✅ <b>All clear.</b> {after != null ? `The shop recovered ${after} s after the fix. ` : ""}All {alerts.length} alarms
        cleared and customers are getting through again. I wrote the incident report and I'll remember this one, so next time I offer the same fix first. Go back to sleep 😴
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="rounded-full border border-eucalyptus/30 bg-white px-3 py-1 text-[13px] text-eucalyptus" onClick={onOpenReport}>Read the report</button>
          {replay && <button className="rounded-full border border-eucalyptus/30 bg-white px-3 py-1 text-[13px] text-eucalyptus" onClick={onStart}>▶ Run it again</button>}
        </div>
      </Bubble>);
  }

  const asking = stage === "fix" && !!fix && !said && !declined && !inFlight;
  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-[30px] border-[9px] border-[#1E2621] bg-[#EFE7DC] shadow-[0_30px_60px_-30px_rgba(40,30,10,0.55)]">
      {/* chat header */}
      <div className="flex items-center gap-3 bg-eucalyptus px-3 py-2.5 text-white">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/90 font-display text-[17px] text-eucalyptus">R</span>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="text-[15px] font-semibold">RootCause</p>
          <p className="text-[12px] text-white/75">{typing || stage === "investigating" || (stage === "fixing" && applied?.status !== "verified") ? "typing…" : "on-call agent · online"}</p>
        </div>
        {replay && demo && (
          <button className="rounded-md bg-white/15 px-2 py-1 font-mono text-[10.5px] hover:bg-white/25" onClick={() => onAutoplay(!autoplay)}>
            {autoplay ? "autoplay on" : "autoplay off"}</button>
        )}
      </div>

      {/* thread */}
      <div ref={body} className="wa-wallpaper flex-1 space-y-2 overflow-y-auto px-3 py-3">
        <p className="mx-auto w-fit rounded-md bg-white/80 px-2 py-0.5 text-[11px] text-[#54656F] shadow-sm">TODAY</p>
        <p className="mx-auto w-[92%] rounded-md bg-[#FFF3C4] px-2.5 py-1.5 text-center text-[11.5px] leading-snug text-[#54656F] shadow-sm">
          🔒 RootCause explains every step and never changes anything without your OK.{inc ? ` Incident ${inc.id}.` : ""}</p>
        {msgs}
        {(typing || stage === "investigating") && !asking && (
          <div className="flex"><div className="rounded-xl rounded-tl-none bg-white px-3 py-2 shadow-sm">
            <span className="typing-dots"><i /><i /><i /></span></div></div>
        )}
        {err && <p className="text-center text-xs text-raspberry">{err}</p>}
      </div>

      {/* reply bar: quick replies when RootCause is asking, otherwise a quiet input */}
      <div className="border-t border-black/5 bg-[#F0F2F5] px-2.5 py-2">
        {asking && fix && fix.risk !== "high" ? (
          <>
            <div className="flex gap-2">
              <button className="flex-1 rounded-full bg-eucalyptus px-3 py-2 text-[14px] font-medium text-white disabled:opacity-50" disabled={busy} onClick={approve}>
                Yes, fix it 👍</button>
              <button className="rounded-full border border-black/10 bg-white px-3 py-2 text-[14px]" disabled={busy}
                      onClick={() => { setDeclined(true); onAutoplay(false); }}>Not now</button>
            </div>
            {canAuto && (
              <p className="mt-1.5 text-center text-[11px] text-[#667781]">Demo autoplay: tapping "Yes" for you in {left} s ·{" "}
                <button className="underline" onClick={() => onAutoplay(false)}>let me decide</button></p>
            )}
          </>
        ) : asking && fix ? (
          <div className="text-[13px]"><p className="mb-1.5 text-center text-[11.5px] text-[#667781]">High risk: confirm by typing below.</p>
            <ActionCard a={fix} onChanged={onChanged} /></div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="flex-1 rounded-full bg-white px-4 py-2 text-[13px] text-[#8696A0]">Message</span>
            <span className="grid h-9 w-9 place-items-center rounded-full bg-eucalyptus text-white">🎙</span>
          </div>
        )}
        {declined && !applied && fix && (
          <button className="mt-2 w-full rounded-full border border-eucalyptus/30 bg-white py-1.5 text-[13px] text-eucalyptus" onClick={() => setDeclined(false)}>
            Actually, fix it</button>
        )}
      </div>
    </div>
  );
}
