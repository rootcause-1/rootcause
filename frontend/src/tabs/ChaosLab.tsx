// Chaos lab: break one fault, a Mystery round (random, hidden), or N blind runs; live scorecard via SSE.
import { useEffect, useState } from "react";
import type { Status } from "../api";
import { api } from "../api";

export type ChaosRun = { id: string; flag: string; truth: string; verdict: string | null; top1: boolean; top3: boolean;
  ttd_ms: number | null; class: string };

export default function ChaosLab({ status, runs }: { status: Status | null; runs: ChaosRun[] }) {
  const [cat, setCat] = useState<{ flag: string; class: string }[]>([]);
  const [flag, setFlag] = useState("");
  const [n, setN] = useState(5);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.catalogue().then(setCat).catch(() => setCat([])); }, []);
  const chaos = status?.chaos;
  const live = status?.mode === "live";

  async function go(body: { n: number; flag?: string; mystery?: boolean }) {
    setErr(null);
    try { await api.chaosRun(body); } catch (e) { setErr((e as Error).message); }
  }
  const t1 = runs.length ? runs.filter((r) => r.top1).length / runs.length : 0;
  const t3 = runs.length ? runs.filter((r) => r.top3).length / runs.length : 0;

  return (
    <div className="grid grid-cols-3 gap-4 p-4">
      <div className="card space-y-3">
        <div className="label">Break something</div>
        {!live && <p className="text-sm text-amber-300">Chaos runs need live mode (the real demo).</p>}
        <select className="w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-sm" value={flag}
                onChange={(e) => setFlag(e.target.value)}>
          <option value="">pick a fault…</option>
          {cat.map((c) => <option key={c.flag} value={c.flag}>{c.flag} ({c.class})</option>)}
        </select>
        <div className="flex gap-2">
          <button className="btn-primary" disabled={!live || !flag || chaos?.running} onClick={() => go({ n: 1, flag })}>Break it</button>
          <button className="btn-ghost" disabled={!live || chaos?.running} onClick={() => go({ n: 1, mystery: true })}>Mystery round</button>
        </div>
        <div className="flex items-center gap-2">
          <input type="number" min={1} max={50} value={n} onChange={(e) => setN(+e.target.value)}
                 className="w-20 rounded border border-slate-700 bg-slate-950 p-1 text-sm" />
          <button className="btn-ghost" disabled={!live || chaos?.running} onClick={() => go({ n })}>Run {n} blind</button>
        </div>
        {chaos?.running && <p className="text-sm text-sky-300">running {chaos.done}/{chaos.total} · {chaos.current}</p>}
        {err && <p className="text-sm text-red-400">{err}</p>}
      </div>
      <div className="card col-span-2">
        <div className="label mb-2">Scorecard (this session) — top-1 {Math.round(t1 * 100)}% · top-3 {Math.round(t3 * 100)}%</div>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400"><tr><th>run</th><th>fault</th><th>truth</th><th>verdict</th><th>top-1</th><th>time</th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="border-t border-slate-800">
                <td className="font-mono text-xs">{r.id}</td><td>{r.flag}</td><td className="font-mono">{r.truth}</td>
                <td className="font-mono">{r.verdict ?? "-"}</td><td>{r.top1 ? "✅" : r.top3 ? "🟡" : "❌"}</td>
                <td>{r.ttd_ms ? `${Math.round(r.ttd_ms / 1000)} s` : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 && <p className="mt-2 text-sm text-slate-400">No runs yet. Full history: docs/SCORECARD.md</p>}
      </div>
    </div>
  );
}
