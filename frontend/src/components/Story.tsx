// The incident, told as a story from top to bottom. Each chapter lights up when the real system reaches it:
// watching -> something broke -> grouped into one incident -> root cause and why -> who is hurt -> the fix -> recovered.
// Upcoming chapters are listed (greyed) so a first-time visitor sees where this is going.
import type { ReactNode } from "react";
import type { Hypothesis, Incident, Status } from "../api";
import { clock, pct } from "../api";
import FixFlow from "./FixFlow";
import TrailDrawer from "./TrailDrawer";

type State = "done" | "active" | "pending";

function Chapter({ n, title, state, children, last }: { n: number; title: string; state: State; children?: ReactNode; last?: boolean }) {
  return (
    <li className={`relative pl-11 ${last ? "" : "pb-6"}`}>
      {!last && <span aria-hidden className="absolute bottom-0 left-[13px] top-8 w-px bg-pine/15" />}
      <span className={`absolute left-0 top-0 grid h-7 w-7 place-items-center rounded-full text-sm font-bold ${
        state === "done" ? "bg-pine text-paper" : state === "active" ? "bg-saffron text-pine ring-4 ring-saffron/25" : "border-2 border-mist text-pine-soft"}`}>
        {state === "done" ? "✓" : n}
      </span>
      <h3 className={`pt-0.5 font-display text-lg font-bold leading-tight ${state === "pending" ? "text-pine-soft/70" : ""}`}>{title}</h3>
      {state !== "pending" && children && <div className="mt-2 text-[15px] leading-relaxed">{children}</div>}
    </li>
  );
}

const KIND: Record<string, string> = {
  error_rate: "errors", latency: "slow responses", lag: "a growing queue backlog", memory: "memory growing",
  cpu: "CPU saturated", agent_loop: "an AI agent looping", llm_latency: "slow AI responses", gc: "garbage-collection pressure",
};

/** Plain-English reasons, read straight off the top hypothesis' five signal scores and the linked change. */
function reasons(h: Hypothesis, inc: Incident): string[] {
  const root = h.target.replace(/^edge:/, "");
  const out: string[] = [];
  if (h.target.startsWith("edge:")) {
    const [a, b] = h.target.slice(5).split("->");
    out.push(`Calls from ${a} to ${b} are going unanswered: ${b} stopped receiving traffic while ${a} keeps failing. The connection is broken, not the code.`);
  }
  if (h.self >= 0.5) out.push(`The failures start inside ${root} itself; its own work fails, not something it calls.`);
  if (h.depth >= 0.99) out.push(`Nothing that ${root} depends on is failing, so the trail of blame stops here.`);
  if (h.pagerank >= 0.5) out.push(`Following "who is failing because of whom" through the call graph, the blame flows to ${root}.`);
  const ch = inc.changes[0];
  if (h.change > 0 && ch) {
    const mins = Math.max(0, Math.round((inc.onset_ts - ch.ts) / 60000));
    out.push(ch.kind === "flag"
      ? `Feature flag ${ch.target} was changed from "${ch.from_variant ?? "?"}" to "${ch.to}" ${mins ? `${mins} min` : "just"} before the alerts started, and it affects ${root}.`
      : `${ch.target} had a ${ch.kind} ${mins ? `${mins} min` : "just"} before the alerts started.`);
  }
  if (h.memory > 0) out.push(`It matches a past incident with the same symptoms (${pct(h.memory)} alike).`);
  return out;
}

export default function Story({ status, inc, reportReady, onChanged, onCite, onBlast, onOpenReport, onStart }: {
  status: Status | null; inc: Incident | null; reportReady: boolean; onChanged: () => void;
  onCite: (ids: string[]) => void; onBlast: (ids: string[]) => void; onOpenReport: () => void; onStart?: () => void;
}) {
  const replay = status?.mode === "replay";
  const learning = (status?.learning_left_ms ?? 0) > 0;
  const has = !!inc;
  const resolved = inc?.status === "resolved";
  const top = inc?.hypotheses[0];
  const investigating = has && !resolved && (!top || inc!.agent_state === "pending" || inc!.agent_state === "investigating");
  const alerts = inc?.alerts ?? [];
  const targets = [...new Set(alerts.map((a) => a.target))];
  const kinds = [...new Set(alerts.map((a) => KIND[a.kind] ?? a.kind))];
  const first = alerts[0]?.ts;
  const hurt = (inc?.impact ?? []).filter((i) => i.pct > 0);
  const fixing = inc?.actions.some((a) => ["approved", "executing", "executed"].includes(a.status));

  const s = (cond: boolean, active: boolean): State => (cond ? "done" : active ? "active" : "pending");

  return (
    <ol>
      <Chapter n={1} title={has ? "Watching the shop" : learning ? "Learning what normal looks like" : "Watching the shop: all healthy"} state={s(has, !has)}>
        {!has && (
          <>
            <p>Every request in the shop becomes nodes and edges in a FalkorDB graph, refreshed every 5 seconds: which
              service calls which, how fast, and how often it fails.
              {learning ? ` Baselines are being learned: ${Math.ceil((status?.learning_left_ms ?? 0) / 1000)} s to go.` : " Nothing is wrong right now."}</p>
            {replay && onStart && (
              <button className="btn-primary mt-3" onClick={onStart}>Watch a run-through from the start</button>
            )}
            {replay && <p className="mt-2 text-sm muted">This replays telemetry recorded from the real OpenTelemetry Demo; a fault starts in about a minute.</p>}
          </>
        )}
      </Chapter>

      <Chapter n={2} title={has ? `Something went wrong: ${alerts.length} alert${alerts.length === 1 ? "" : "s"} fired` : "Something goes wrong"} state={s(has, false)}>
        <p>{kinds.join(", ")} on <b>{targets.join(", ")}</b>{first ? `, starting at ${clock(first)}` : ""}.</p>
      </Chapter>

      <Chapter n={3} title={has ? `${alerts.length} alerts became 1 incident` : "The alerts become one incident"} state={s(has, false)}>
        <p>These services are connected in the call graph and are failing because of one another, so RootCause opened a
          single incident (<b>{inc?.id}</b>) instead of paging you {alerts.length} times.</p>
      </Chapter>

      <Chapter n={4} title={top && !investigating ? `Root cause: ${top.target.replace(/^edge:/, "")}` : "Find the root cause"}
               state={s(!!top && !investigating, investigating)}>
        {investigating ? (
          <p className="flex items-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-saffron border-t-transparent" />
            The agent is investigating{inc?.steps.length ? `: ${inc.steps.length} step${inc.steps.length === 1 ? "" : "s"} so far` : "…"}</p>
        ) : top && inc && (
          <>
            <p>Ranked first of {inc.hypotheses.length} suspects with a confidence of <b>{top.score.toFixed(2)}</b> out of 1,
              from five signals in the graph.</p>
            <p className="mt-3 text-sm font-semibold">Why {top.target.replace(/^edge:/, "")}?</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-[15px]">{reasons(top, inc).map((r) => <li key={r}>{r}</li>)}</ul>
            {inc.evidence_path.length > 1 && (
              <>
                <p className="mt-3 text-sm font-semibold">The evidence trail (highlighted on the map)</p>
                <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm">
                  {inc.evidence_path.map((n, i) => (
                    <span key={n} className="flex items-center gap-1.5">
                      <span className={`rounded-full px-2.5 py-0.5 ${i === inc.evidence_path.length - 1 ? "bg-raspberry font-semibold text-paper" : "bg-saffron/20"}`}>{n}</span>
                      {i < inc.evidence_path.length - 1 && <span aria-hidden className="muted">→</span>}
                    </span>
                  ))}
                </p>
              </>
            )}
            {inc.hypotheses.length > 1 && (
              <p className="mt-3 text-sm muted">Also considered: {inc.hypotheses.slice(1, 4).map((h) => `${h.target.replace(/^edge:/, "")} (${h.score.toFixed(2)})`).join(", ")}.</p>
            )}
            {inc.steps.length > 0 && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-semibold">How the agent got there ({inc.steps.length} steps, hover to see what each one looked at)</summary>
                <div className="mt-2"><TrailDrawer steps={inc.steps} onHover={onCite} /></div>
              </details>
            )}
          </>
        )}
      </Chapter>

      <Chapter n={5} title="Who is affected" state={s(!!top && !investigating, false)}>
        {hurt.length ? hurt.map((i) => (
          <div key={i.journey} className="mb-2">
            <div className="flex justify-between text-[15px]"><span>Customers trying to <b>{i.journey.replace("journey:", "").replace(/_/g, " ")}</b></span>
              <b className="text-raspberry">success down {pct(i.pct)}</b></div>
            <div className="mt-1 h-1.5 rounded-full bg-mist/60"><div className="h-1.5 rounded-full bg-raspberry" style={{ width: pct(i.pct) }} /></div>
          </div>
        )) : <p>No customer journey has dropped measurably yet.</p>}
      </Chapter>

      <Chapter n={6} title={resolved ? "Fixed" : fixing ? "Fixing it" : "Fix it, with your approval"} state={s(resolved, !!top && !investigating)}>
        {inc && <FixFlow inc={inc} replay={replay} reportReady={reportReady} onChanged={onChanged} onBlast={onBlast} onOpenReport={onOpenReport} />}
      </Chapter>

      <Chapter n={7} title="Back to normal" state={s(resolved, false)} last>
        {inc && (() => {
          const fix = inc.actions.find((a) => a.executed_ts);
          const afterFix = fix?.executed_ts && inc.resolved_ts ? Math.round((inc.resolved_ts - fix.executed_ts) / 1000) : null;
          return (
            <p>{afterFix != null ? `Recovered ${afterFix} s after the fix was applied` : "Recovered"}
              {inc.ttr_ms ? ` (${Math.round(inc.ttr_ms / 1000)} s after the incident opened)` : ""}. The errors have calmed down
              (see the timeline above the map), and this incident's fingerprint is remembered, so next time the same fix is offered first.</p>
          );
        })()}
      </Chapter>
    </ol>
  );
}
