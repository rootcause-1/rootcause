// One proposed action: what it does, its risk and side effects, Approve / Reject.
// High risk needs the typed confirmation (e.g. "RESTART payment").
import { useState } from "react";
import type { Action } from "../api";
import { api } from "../api";

const RISK: Record<string, string> = {
  none: "bg-mist text-pine", low: "bg-eucalyptus/20 text-pine", medium: "bg-saffron/20 text-pine", high: "bg-raspberry/15 text-raspberry",
};
const VERB: Record<string, string> = { flag_revert: "Revert flag", restart: "Restart", automation: "Run automation", page: "Page" };
const DONE: Record<string, string> = { executed: "Applied, watching recovery…", verified: "Applied and verified: it recovered.",
  failed: "Applied, but it did not recover.", approved: "Approved, applying…" };

export default function ActionCard({ a, onChanged, closed }: { a: Action; onChanged: () => void; closed?: boolean }) {
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const phrase = a.risk !== "high" ? null : a.kind === "automation" ? `RUN ${a.target}` : `RESTART ${a.target}`;
  const proposed = a.status === "proposed" && !closed;

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setErr(null);
    try { await fn(); onChanged(); } catch (e) { setErr(String((e as Error).message)); } finally { setBusy(false); }
  }

  const se = a.side_effects ?? {};
  const verb = VERB[a.kind] ?? a.kind.replace("_", " ");
  return (
    <div className={`rounded-2xl border p-3.5 ${a.rank === 1 && proposed ? "border-pine/30 bg-paper" : "border-pine/10 bg-porcelain/60"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[15px] font-semibold">{verb} {a.target}</span>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${RISK[a.risk] ?? "bg-mist"}`}>{a.risk} risk</span>
      </div>
      <p className="mt-1 text-sm muted">{a.reason}</p>
      {(se.affected_services?.length ?? 0) > 0 && (
        <p className="mt-0.5 text-xs muted">Touches {se.affected_services!.join(", ")}
          {se.affected_journeys?.length ? `; journeys ${se.affected_journeys.map((j) => j.replace("journey:", "")).join(", ")}` : ""}
          {se.stateful ? "; holds state" : ""}.</p>
      )}
      {proposed ? (
        <div className="mt-3 flex items-center gap-2">
          {phrase && (
            <input className="field min-w-0 flex-1" aria-label={`Type ${phrase} to confirm`}
                   placeholder={`Type ${phrase} to confirm`} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          )}
          <button className="btn-primary" disabled={busy || (!!phrase && confirm !== phrase)}
                  onClick={() => run(() => api.approve(a.id, phrase ? confirm : undefined))}>Approve {verb.toLowerCase()}</button>
          <button className="btn-ghost" disabled={busy} onClick={() => run(() => api.reject(a.id))}>Reject</button>
        </div>
      ) : (
        <p className={`mt-2 text-sm font-medium ${a.status === "failed" ? "text-raspberry" : "text-pine"}`}>
          {a.status === "proposed" && closed ? "Not needed: the incident is resolved." : DONE[a.status] ?? a.status}</p>
      )}
      {err && <p className="mt-1 text-sm text-raspberry">{err}</p>}
    </div>
  );
}
