// Reports: post-incident reports stored as (:Report) nodes, shown as their markdown source.
import { useEffect, useState } from "react";
import { api, clock } from "../api";

type Rep = Awaited<ReturnType<typeof api.reports>>[number];

export default function Reports() {
  const [rows, setRows] = useState<Rep[]>([]);
  const [sel, setSel] = useState<Rep | null>(null);
  useEffect(() => { api.reports().then((r) => { setRows(r); setSel(r[0] ?? null); }).catch(() => setRows([])); }, []);
  return (
    <div className="grid grid-cols-4 gap-4 p-4">
      <div className="card">
        <div className="label mb-2">Reports</div>
        {rows.map((r) => (
          <button key={r.id} onClick={() => setSel(r)}
                  className={`block w-full rounded px-2 py-1 text-left text-sm hover:bg-slate-800 ${sel?.id === r.id ? "bg-slate-800" : ""}`}>
            {r.incident}<span className="block text-xs text-slate-400">{clock(r.ts)}</span>
          </button>
        ))}
        {rows.length === 0 && <p className="text-sm text-slate-400">No reports yet.</p>}
      </div>
      <pre className="card col-span-3 overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">{sel?.markdown ?? ""}</pre>
    </div>
  );
}
