// Reports: post-incident reports stored as (:Report) nodes. The markdown is rendered with a tiny renderer that only
// knows what actions/report.py writes (headings, bullet lists, tables, **bold**, `code`); no HTML is ever injected.
import { Fragment, ReactNode, useEffect, useState } from "react";
import { api, clock } from "../api";

type Rep = Awaited<ReturnType<typeof api.reports>>[number];

function inline(text: string): ReactNode[] {
  // split on **bold** and `code`; everything else is plain text
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, i) => {
    if (part.startsWith("**")) return <strong key={i} className="text-pine">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`")) return <code key={i} className="rounded-md bg-saffron/15 px-1.5 font-medium text-pine">{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

function Markdown({ md }: { md: string }) {
  const out: ReactNode[] = [];
  const lines = md.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("# ")) out.push(<h2 key={i} className="mb-3 font-display text-3xl font-bold tracking-tight">{inline(line.slice(2))}</h2>);
    else if (line.startsWith("## ")) out.push(<h3 key={i} className="section-title mt-5">{inline(line.slice(3))}</h3>);
    else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) items.push(lines[i++].slice(2));
      i--;
      out.push(<ul key={i} className="ml-4 list-disc space-y-0.5 text-sm">{items.map((t, k) => <li key={k}>{inline(t)}</li>)}</ul>);
    } else if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i++].split("|").slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells);
      }
      i--;
      const [head, ...body] = rows;
      out.push(
        <table key={i} className="my-1 text-sm">
          <thead><tr>{head.map((c, k) => <th key={k} className="pr-4 text-left text-xs muted">{inline(c)}</th>)}</tr></thead>
          <tbody>{body.map((r, k) => <tr key={k}>{r.map((c, m) => <td key={m} className="border-t border-pine/10 py-1 pr-4">{inline(c)}</td>)}</tr>)}</tbody>
        </table>);
    } else if (line.trim()) out.push(<p key={i} className="text-sm">{inline(line)}</p>);
  }
  return <div className="space-y-1">{out}</div>;
}

export default function Reports() {
  const [rows, setRows] = useState<Rep[] | null>(null);
  const [sel, setSel] = useState<Rep | null>(null);
  useEffect(() => { api.reports().then((r) => { setRows(r); setSel(r[0] ?? null); }).catch(() => setRows([])); }, []);
  return (
    <div className="grid grid-cols-[180px_1fr] gap-6">
      <div>
        <h3 className="section-title">Reports</h3>
        {rows === null && <p className="text-sm muted">Loading…</p>}
        {(rows ?? []).map((r) => (
          <button key={r.id} onClick={() => setSel(r)}
                  className={`block w-full rounded-xl px-3 py-1.5 text-left text-sm hover:bg-pine/5 ${sel?.id === r.id ? "bg-pine/10 font-semibold" : ""}`}>
            {r.incident}<span className="block text-xs font-normal muted">{clock(r.ts)}</span>
          </button>
        ))}
        {rows?.length === 0 && <p className="text-sm muted">No reports yet. One is written when an incident is fixed.</p>}
      </div>
      <div className="min-w-0">{sel ? <Markdown md={sel.markdown} /> : null}</div>
    </div>
  );
}
