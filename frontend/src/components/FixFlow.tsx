// "Should I fix this?" -> review the plan -> watch each step happen. Everything shown is the real state of the
// Action and Incident nodes: approve mints a single-use token and executes (POST /api/actions/{id}/approve);
// verification (actions/verify.py) resolves the incident once every alert has cleared; then the report is written.
import { useEffect, useState } from "react";
import type { Action, Incident } from "../api";
import { api } from "../api";
import ActionCard from "./ActionCard";

export function describe(a: Action): string {
  if (a.kind === "flag_revert") return `Switch feature flag ${a.target} back to "${String(a.params?.variant ?? "off")}"`;
  if (a.kind === "restart") return `Restart the ${a.target} container`;
  if (a.kind === "page") return `Page ${a.target}`;
  return `${a.kind.replace(/_/g, " ")} ${a.target}`;
}

const APPLIED = new Set(["approved", "executing", "executed", "verified", "failed"]);

type Mark = "done" | "active" | "pending" | "failed";
function Check({ mark, children, note }: { mark: Mark; children: React.ReactNode; note?: React.ReactNode }) {
  const icon = mark === "done" ? <span className="grid h-5 w-5 place-items-center rounded-full bg-eucalyptus text-[11px] text-paper">✓</span>
    : mark === "failed" ? <span className="grid h-5 w-5 place-items-center rounded-full bg-raspberry text-[11px] text-paper">✕</span>
    : mark === "active" ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-saffron border-t-transparent" />
    : <span className="h-5 w-5 rounded-full border-2 border-mist" />;
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className={mark === "pending" ? "muted" : ""}><div className="text-[15px]">{children}</div>
        {note && <div className="text-xs muted">{note}</div>}</div>
    </li>
  );
}

export default function FixFlow({ inc, replay, reportReady, onChanged, onBlast, onOpenReport }: {
  inc: Incident; replay: boolean; reportReady: boolean; onChanged: () => void;
  onBlast: (ids: string[]) => void; onOpenReport: () => void;
}) {
  const actions = inc.actions.filter((a) => a.status !== "rejected");
  const applied = [...actions].reverse().find((a) => APPLIED.has(a.status) && a.kind !== "page");
  const proposed = actions.filter((a) => a.status === "proposed");
  const fixes = proposed.filter((a) => a.kind !== "page");
  const top = fixes[0] ?? proposed[0];
  const [stage, setStage] = useState<"ask" | "review" | "later">("ask");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setStage("ask"); setConfirm(""); setErr(null); }, [top?.id]);
  useEffect(() => { onBlast(stage === "review" && top ? top.side_effects?.affected_services ?? [] : []); }, [stage, top?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const resolved = inc.status === "resolved";
  const phrase = top?.risk === "high" ? `RESTART ${top.target}` : null;

  async function apply() {
    if (!top) return;
    setBusy(true); setErr(null);
    try { await api.approve(top.id, phrase ? confirm : undefined); setStage("ask"); onChanged(); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  // ---- a fix is (or was) being applied: show each step as it really happens
  if (applied && (applied.status !== "failed" || !top)) {
    const total = inc.alerts.length;
    const cleared = inc.alerts.filter((a) => a.status === "resolved").length;
    const s = applied.status;
    const ran = s === "executed" || s === "verified" || s === "failed";
    const ok = s === "verified" || resolved;
    return (
      <ol className="space-y-3">
        <Check mark="done">You approved: {describe(applied)}</Check>
        <Check mark={ran ? "done" : "active"} note={replay && ran ? "In this replay the change is simulated; the recovery below is the one recorded from the real demo." : undefined}>
          {ran ? "Applied the change" : "Applying the change…"}
        </Check>
        <Check mark={ok ? "done" : s === "failed" ? "failed" : ran ? "active" : "pending"}
               note={ran && !ok && s !== "failed" ? "Alerts clear after 3 healthy checks in a row (15 s); I give it up to 90 s." : undefined}>
          {ok ? "Errors stopped: every alert has cleared" : `Watching recovery: ${cleared} of ${total} alerts cleared`}
        </Check>
        <Check mark={ok ? "done" : s === "failed" ? "failed" : "pending"}>
          {s === "failed" ? "It did not recover in time" : "Verified: the incident is resolved"}
        </Check>
        <Check mark={reportReady ? "done" : ok ? "active" : "pending"}>
          {reportReady ? <>Wrote the post-incident report. <button className="font-semibold underline" onClick={onOpenReport}>Read it</button></> : "Writing the post-incident report"}
        </Check>
      </ol>
    );
  }

  if (resolved) return <p className="text-[15px]">It recovered on its own before anything was changed.</p>;
  if (!top) return <p className="text-[15px] muted">Working out what to do…</p>;

  const failedBefore = actions.find((a) => a.status === "failed");
  const others = proposed.filter((a) => a.id !== top.id);
  return (
    <div className="space-y-4">
      {failedBefore && <p className="rounded-xl bg-raspberry/10 px-3 py-2 text-sm text-raspberry">
        {describe(failedBefore)} did not bring it back, so here is the next option.</p>}

      {stage === "ask" && (
        <div className="rounded-2xl border-2 border-pine/80 bg-paper p-4">
          <p className="text-xs font-semibold uppercase tracking-wide muted">Recommended fix · {top.risk} risk</p>
          <p className="mt-1 font-display text-xl font-bold leading-snug">{describe(top)}</p>
          <p className="mt-1 text-sm muted">{top.reason}</p>
          <p className="mt-4 text-[15px] font-semibold">Should I fix this?</p>
          <div className="mt-2 flex gap-2">
            <button className="btn-primary" onClick={() => setStage("review")}>Yes, fix it</button>
            <button className="btn-ghost" onClick={() => setStage("later")}>Not now</button>
          </div>
        </div>
      )}

      {stage === "later" && (
        <div className="rounded-2xl border border-pine/15 bg-porcelain/60 p-4">
          <p className="text-[15px]">Okay, I won't change anything. The incident stays open and the alerts keep firing.</p>
          <button className="btn-ghost mt-3" onClick={() => setStage("ask")}>Fix it after all</button>
        </div>
      )}

      {stage === "review" && (
        <div className="rounded-2xl border-2 border-pine/80 bg-paper p-4">
          <p className="font-display text-lg font-bold">Before I change anything</p>
          <ol className="mt-3 space-y-2.5">
            <Check mark="done" note={top.reason}>What I will do: <b>{describe(top)}</b></Check>
            <Check mark="done" note="Ringed in blue on the map.">
              What it touches: {top.side_effects?.affected_services?.length ? top.side_effects.affected_services.join(", ") : "nothing else"}
              {top.side_effects?.affected_journeys?.length ? ` (journeys: ${top.side_effects.affected_journeys.map((j) => j.replace("journey:", "")).join(", ")})` : ""}
            </Check>
            <Check mark="done" note={top.side_effects?.reason}>Risk: <b>{top.risk}</b>{top.side_effects?.stateful ? ", it holds session state" : ""}</Check>
            <Check mark="done">How I'll know it worked: all {inc.alerts.length} alerts clear and stay clear</Check>
            <Check mark="done">If it doesn't: I stop and propose the next option. Nothing else changes without you.</Check>
          </ol>
          {phrase && (
            <input className="field mt-4 w-full" placeholder={`High risk: type ${phrase} to confirm`} aria-label={`Type ${phrase} to confirm`}
                   value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          )}
          <div className="mt-4 flex gap-2">
            <button className="btn-primary" disabled={busy || (!!phrase && confirm !== phrase)} onClick={apply}>
              {busy ? "Applying…" : "Confirm and apply"}
            </button>
            <button className="btn-ghost" disabled={busy} onClick={() => setStage("ask")}>Back</button>
          </div>
          {err && <p className="mt-2 text-sm text-raspberry">{err}</p>}
        </div>
      )}

      {others.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">Other options ({others.length})</summary>
          <div className="mt-2 space-y-2">{others.map((a) => <ActionCard key={a.id} a={a} onChanged={onChanged} />)}</div>
        </details>
      )}
    </div>
  );
}
