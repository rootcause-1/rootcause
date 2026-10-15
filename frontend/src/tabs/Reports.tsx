// Reports: post-incident reports stored as (:Report) nodes. The markdown is rendered with a tiny renderer that only
// knows what actions/report.py writes (headings, bullet lists, tables, **bold**, `code`); no HTML is ever injected.
import { Fragment, ReactNode, useEffect, useState } from "react";
import { api, clock } from "../api";

type Rep = Awaited<ReturnType<typeof api.reports>>[number];

function inline(text: string): ReactNode[] {
  // split on **bold** and `code`; everything else is plain text
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, i) => {
    if (part.startsWith("**")) return <strong key={i} className="text-slate-100">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`")) return <code key={i} className="rounded bg-slate-800 px-1 text-amber-200">{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

function Markdown({ md }: { md: string }) {
  const out: ReactNode[] = [];
  const lines = md.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("# ")) out.push(<h2 key={i} className="mb-3 text-lg font-bold">{inline(line.slice(2))}</h2>);
    else if (line.startsWith("## ")) out.push(<h3 key={i} className="label mb-1 mt-4">{inline(line.slice(3))}</h3>);
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
          <thead><tr>{head.map((c, k) => <th key={k} className="pr-4 text-left text-slate-400">{inline(c)}</th>)}</tr></thead>
          <tbody>{body.map((r, k) => <tr key={k}>{r.map((c, m) => <td key={m} className="pr-4 font-mono">{inline(c)}</td>)}</tr>)}</tbody>
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
    <div className="grid grid-cols-4 gap-4 p-4">
      <div className="card">
        <div className="label mb-2">Reports</div>
        {rows === null && <p className="text-sm text-slate-400">Loading…</p>}
        {(rows ?? []).map((r) => (
          <button key={r.id} onClick={() => setSel(r)}
                  className={`block w-full rounded px-2 py-1 text-left text-sm hover:bg-slate-800 ${sel?.id === r.id ? "bg-slate-800" : ""}`}>
            {r.incident}<span className="block text-xs text-slate-400">{clock(r.ts)}</span>
          </button>
        ))}
        {rows?.length === 0 && <p className="text-sm text-slate-400">No reports yet.</p>}
      </div>
      <div className="card col-span-3 overflow-auto">{sel ? <Markdown md={sel.markdown} /> : null}</div>
    </div>
  );
}
