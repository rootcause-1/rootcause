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
    <div className="space-y-6">
      <header>
        <h2 className="font-display text-3xl font-bold tracking-tight">Break something</h2>
        <p className="mt-1 max-w-[60ch] muted">Flip one of the demo's fault flags and watch RootCause find it. A mystery round
          picks the fault at random and does not tell you which.</p>
      </header>
      {!live && <p className="rounded-xl bg-saffron/15 px-3 py-2 text-sm">Chaos runs need live mode, with the real OpenTelemetry Demo running.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <select className="field" value={flag} onChange={(e) => setFlag(e.target.value)} aria-label="Fault to inject">
          <option value="">Pick a fault…</option>
          {cat.map((c) => <option key={c.flag} value={c.flag}>{c.flag} ({c.class})</option>)}
        </select>
        <button className="btn-primary" disabled={!live || !flag || chaos?.running} onClick={() => go({ n: 1, flag })}>Break it</button>
        <button className="btn-ghost" disabled={!live || chaos?.running} onClick={() => go({ n: 1, mystery: true })}>Mystery round</button>
        <span className="mx-2 h-6 w-px bg-pine/15" aria-hidden />
        <input type="number" min={1} max={50} value={n} onChange={(e) => setN(+e.target.value)} className="field w-20" aria-label="Number of blind runs" />
        <button className="btn-ghost" disabled={!live || chaos?.running} onClick={() => go({ n })}>Run {n} blind</button>
      </div>
      {chaos?.running && <p className="text-sm">Running {chaos.done} of {chaos.total}{chaos.current ? `: ${chaos.current}` : ""}.</p>}
      {err && <p className="text-sm text-raspberry">{err}</p>}

      <section>
        <h3 className="section-title">This session</h3>
        {runs.length > 0 && (
          <p className="mb-3 font-display text-4xl font-bold">{Math.round(t1 * 100)} % <span className="text-lg font-medium muted">found first, {Math.round(t3 * 100)} % in the top three</span></p>
        )}
        {runs.length > 0 ? (
          <table className="w-full text-sm">
            <thead className="text-left text-xs muted"><tr><th className="py-1">Fault</th><th>Truth</th><th>RootCause said</th><th>Found</th><th>Time</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-pine/10">
                  <td className="py-1.5">{r.flag}</td><td>{r.truth}</td><td className="font-medium">{r.verdict ?? "nothing"}</td>
                  <td className={r.top1 ? "text-pine" : r.top3 ? "text-saffron" : "text-raspberry"}>{r.top1 ? "first" : r.top3 ? "top three" : "missed"}</td>
                  <td>{r.ttd_ms ? `${Math.round(r.ttd_ms / 1000)} s` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="text-sm muted">No runs yet in this session. The full blind scorecard is in docs/SCORECARD.md.</p>}
      </section>
    </div>
  );
}
