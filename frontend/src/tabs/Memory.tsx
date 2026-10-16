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
    <div className="space-y-6">
      <header>
        <h2 className="font-display text-3xl font-bold tracking-tight">What RootCause remembers</h2>
        <p className="mt-1 max-w-[60ch] muted">Every resolved incident keeps its signal fingerprint and the fix that worked,
          so the next similar incident starts from the answer.</p>
      </header>
      {rows.length > 0 ? (
        <table className="w-full text-sm">
          <thead className="text-left text-xs muted"><tr><th className="py-1">Incident</th><th>Cause</th><th>Signals</th><th>Fixed by</th><th>Took</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-pine/10 align-top">
                <td className="py-1.5 font-medium">{r.id}</td><td>{r.root}</td>
                <td className="text-xs muted">{r.signals.join(", ")}</td><td className="text-xs">{r.fixes.join(", ") || "recovered on its own"}</td>
                <td>{r.ttr_ms ? `${Math.round(r.ttr_ms / 1000)} s` : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="text-sm muted">Nothing resolved yet.</p>}
      <section>
        <h3 className="section-title">Pages sent</h3>
        {pages.map((p, i) => (
          <p key={i} className="mb-2 text-sm"><b>{p.team}</b> about {p.incident}
            <span className="block text-xs muted">{clock(p.ts)}: {p.message}</span></p>
        ))}
        {pages.length === 0 && <p className="text-sm muted">No one has been paged.</p>}
      </section>
    </div>
  );
}
