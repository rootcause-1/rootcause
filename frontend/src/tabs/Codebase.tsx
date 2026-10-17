// Codebase: connect a GitHub repository. RootCause reads it (never runs it) and puts it in the same FalkorDB graph as
// the running system: which folder implements which service, what each declares it depends on, where feature flags
// are read, the latest commits, and where code and traffic disagree.
import { useEffect, useState } from "react";
import { api, codeLink, type CodeOverview } from "../api";
import { nameOf } from "../components/ServiceMap";

const day = (ts: number | null) => (ts ? new Date(ts).toLocaleDateString([], { day: "numeric", month: "short" }) : "–");

export default function Codebase() {
  const [c, setC] = useState<CodeOverview | null>(null);
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const load = () => api.code().then((x) => { setC(x); setUrl((u) => u || x.repo || x.suggested || ""); }).catch((e) => setErr(String(e.message ?? e)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!c?.scan.running) return;
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [c?.scan.running]);

  const scan = () => { setErr(""); api.scanCode(url).then(load).catch((e) => setErr(String(e.message ?? e))); };
  const code = (c?.modules ?? []).filter((m) => m.files > 0);
  const langs = new Set(code.map((m) => m.language));
  const undeclared = (c?.drift ?? []).filter((d) => d.kind === "undeclared");
  const unused = (c?.drift ?? []).filter((d) => d.kind === "unused");

  return (
    <div className="space-y-6">
      <header>
        <h2 className="font-display text-3xl font-bold tracking-tight">Your codebase</h2>
        <p className="mt-1 max-w-[62ch] muted">Paste your GitHub repository. RootCause reads it (it never runs it) and adds it to the
          same FalkorDB graph as the live system, so an incident can point straight at the code behind it.</p>
        <ul className="mt-3 space-y-1 font-mono text-[11.5px] muted">
          <li>(:CodeModule)-[:IMPLEMENTS]-&gt;(:Service) &nbsp;→ which folder runs as which service</li>
          <li>(:CodeModule)-[:DECLARES]-&gt;(:CodeModule) → dependencies written in the repo</li>
          <li>(:FeatureFlag)-[:READ_IN {"{file, line}"}]-&gt;(:CodeModule) → where a flag changes behaviour</li>
          <li>(:Commit)-[:TOUCHED]-&gt;(:CodeModule) &nbsp;→ latest changes to that code</li>
        </ul>
        <div className="mt-3 flex gap-2">
          <input className="field min-w-0 flex-1 font-mono text-xs" aria-label="GitHub repository URL" placeholder="https://github.com/owner/repo"
                 value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn-primary" disabled={!url || c?.scan.running} onClick={scan}>{c?.scan.running ? "Scanning…" : "Scan"}</button>
        </div>
        {c?.allowed && <p className="mt-1.5 text-xs muted">Public demo site: only {c.allowed.join(", ")} can be scanned here. Run RootCause yourself to scan your own repo.</p>}
        {(err || c?.scan.error) && <p className="mt-1.5 text-xs text-raspberry">{err || c?.scan.error}</p>}
      </header>

      {c?.repo ? (
        <>
          <section className="grid grid-cols-4 gap-2 text-center">
            {[[code.length, "services with code"], [code.reduce((s, m) => s + m.loc, 0).toLocaleString(), "lines read"],
              [langs.size, "languages"], [c.modules.reduce((s, m) => s + m.flags.length, 0), "flag reads"]].map(([v, l]) => (
              <div key={String(l)} className="rounded-xl border border-mist bg-white px-2 py-2.5">
                <p className="font-display text-2xl font-bold">{v}</p><p className="text-[11px] muted">{l}</p>
              </div>
            ))}
          </section>
          <p className="text-xs muted">
            <a className="underline" href={c.repo} target="_blank" rel="noreferrer">{c.repo.replace("https://github.com/", "")}</a> at{" "}
            <span className="font-mono">{c.sha?.slice(0, 7)}</span>, scanned {day(c.scanned_ts)}
          </p>

          <section>
            <h3 className="section-title">Services and their code</h3>
            <table className="w-full text-[13px]">
              <thead className="text-left text-[11px] muted"><tr><th className="py-1">Service</th><th>Code</th><th>Lines</th><th>Flags read</th><th>Last commit</th></tr></thead>
              <tbody>
                {code.map((m) => (
                  <tr key={m.name} className="border-t border-pine/10 align-top">
                    <td className="py-1.5 pr-2 font-medium">{m.implements.length ? m.implements.map(nameOf).join(", ") : <span className="muted">{m.name}</span>}</td>
                    <td className="pr-2"><a className="font-mono text-[11.5px] underline decoration-mist" href={codeLink(c.repo!, c.sha, m.path ?? "")} target="_blank" rel="noreferrer">{m.path}</a>
                      <span className="block text-[11px] muted">{m.language}</span></td>
                    <td className="tabular-nums">{m.loc.toLocaleString()}</td>
                    <td className="text-[11.5px]">{m.flags.join(", ") || <span className="muted">–</span>}</td>
                    <td className="text-[11.5px] muted">{day(m.last_commit_ts)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="section-title">Where the code and the traffic disagree</h3>
            <p className="mb-2 text-xs muted">Compares what the repo declares with the calls RootCause sees live. Undeclared calls are often the
              dependencies nobody remembers until they break.</p>
            {undeclared.length === 0 && unused.length === 0 && <p className="text-sm muted">No disagreement found (or no traffic seen yet).</p>}
            {undeclared.map((d) => <p key={"u" + d.src + d.dst} className="text-[13px]">⚠️ {nameOf(d.src)} calls <b>{nameOf(d.dst)}</b> in traffic, but the repo never declares it</p>)}
            {unused.map((d) => <p key={"n" + d.src + d.dst} className="text-[13px] muted">· {nameOf(d.src)} declares {nameOf(d.dst)}, never called in the last minute</p>)}
          </section>
        </>
      ) : !c?.scan.running && <p className="text-sm muted">No repository scanned yet.</p>}
      {c?.scan.running && <p className="text-sm muted">Cloning and reading {c.scan.url}… (about 20 s)</p>}
    </div>
  );
}
