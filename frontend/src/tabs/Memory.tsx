// Memory: resolved incidents with their signal fingerprints, fixes and similar incidents; plus the pager inbox.
import { useEffect, useState } from "react";
import { api, clock } from "../api";

type Mem = Awaited<ReturnType<typeof api.memory>>;
type Page = Awaited<ReturnType<typeof api.pager>>;

export default function Memory() {
  const [rows, setRows] = useState<Mem>([]);
  const [pages, setPages] = useState<Page>([]);
  useEffect(() => {
    api.memory().then(setRows).catch(() => setRows([]));
    api.pager().then(setPages).catch(() => setPages([]));
  }, []);
  return (
    <div className="grid grid-cols-3 gap-4 p-4">
      <div className="card col-span-2">
        <div className="label mb-2">Incident memory</div>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400"><tr><th>incident</th><th>root</th><th>signals</th><th>fixed by</th><th>ttr</th><th>similar</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-800 align-top">
                <td className="font-mono">{r.id}</td><td className="font-mono">{r.root}</td>
                <td className="text-xs">{r.signals.join(", ")}</td><td className="text-xs">{r.fixes.join(", ") || "-"}</td>
                <td>{r.ttr_ms ? `${Math.round(r.ttr_ms / 1000)} s` : "-"}</td><td className="font-mono text-xs">{r.similar.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="text-sm text-slate-400">No resolved incidents yet.</p>}
      </div>
      <div className="card">
        <div className="label mb-2">Pager inbox</div>
        {pages.map((p, i) => (
          <p key={i} className="mb-2 text-sm"><span className="font-mono">{p.team}</span> · {p.incident}
            <span className="block text-xs text-slate-400">{clock(p.ts)} — {p.message}</span></p>
        ))}
        {pages.length === 0 && <p className="text-sm text-slate-400">No pages sent.</p>}
      </div>
    </div>
  );
}
