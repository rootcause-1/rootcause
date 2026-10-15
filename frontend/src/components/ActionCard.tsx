// One proposed action: risk badge, side effects, Approve / Reject. High risk needs typed confirmation.
import { useState } from "react";
import type { Action } from "../api";
import { api } from "../api";

const RISK: Record<string, string> = { none: "bg-slate-600", low: "bg-emerald-700", medium: "bg-amber-600", high: "bg-red-700" };

export default function ActionCard({ a, onChanged }: { a: Action; onChanged: () => void }) {
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const phrase = a.risk === "high" ? `RESTART ${a.target}` : null;
  const proposed = a.status === "proposed";

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setErr(null);
    try { await fn(); onChanged(); } catch (e) { setErr(String((e as Error).message)); } finally { setBusy(false); }
  }

  const se = a.side_effects ?? {};
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <span className="font-medium">{a.kind.replace("_", " ")} <span className="font-mono">{a.target}</span></span>
        <span className={`rounded px-2 py-0.5 text-xs ${RISK[a.risk] ?? "bg-slate-600"}`}>risk {a.risk}</span>
      </div>
      <p className="mt-1 text-xs text-slate-300">{a.reason}</p>
      {se.reason && <p className="text-xs text-slate-400">{se.reason}</p>}
      {(se.affected_services?.length ?? 0) > 0 && (
        <p className="text-xs text-slate-400">affects: {se.affected_services!.join(", ")}
          {se.affected_journeys?.length ? ` · journeys ${se.affected_journeys.join(", ")}` : ""}
          {se.stateful ? " · stateful" : ""}</p>
      )}
      {proposed ? (
        <div className="mt-2 flex items-center gap-2">
          {phrase && (
            <input className="flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-xs"
                   placeholder={`type ${phrase}`} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          )}
          <button className="btn-primary" disabled={busy || (!!phrase && confirm !== phrase)}
                  onClick={() => run(() => api.approve(a.id, phrase ? confirm : undefined))}>Approve</button>
          <button className="btn-ghost" disabled={busy} onClick={() => run(() => api.reject(a.id))}>Reject</button>
        </div>
      ) : (
        <p className="mt-2 text-xs text-sky-300">status: {a.status}</p>
      )}
      {err && <p className="mt-1 text-xs text-red-400">{err}</p>}
    </div>
  );
}
