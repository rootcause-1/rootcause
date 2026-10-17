// Your company: teams, who is on call, what each team owns, customer journeys and runbooks (with optional automation
// hooks). Everything is stored in the FalkorDB graph, so an edit changes the next incident's paging, impact and fixes.
import { useEffect, useState } from "react";
import { api, type Company, type CompanyRunbook, type CompanyTeam } from "../api";
import { nameOf } from "../components/ServiceMap";

const lines = (s: string) => s.split(/\n|,/).map((x) => x.trim()).filter(Boolean);

function Saver({ onSave, onDelete }: { onSave: () => Promise<unknown>; onDelete?: () => Promise<unknown> }) {
  const [state, setState] = useState<"" | "saving" | "saved" | string>("");
  const go = (f: () => Promise<unknown>, done: string) => {
    setState("saving");
    f().then(() => setState(done)).catch((e) => setState(String(e.message ?? e)));
  };
  return (
    <div className="mt-2 flex items-center gap-2">
      <button className="btn-primary !px-3 !py-1" disabled={state === "saving"} onClick={() => go(onSave, "saved")}>Save</button>
      {onDelete && <button className="btn-ghost !px-3 !py-1" onClick={() => go(onDelete, "deleted")}>Delete</button>}
      {state && state !== "saving" && <span className={`text-xs ${state === "saved" || state === "deleted" ? "text-eucalyptus" : "text-raspberry"}`}>{state}</span>}
    </div>
  );
}

function TeamCard({ team, services, onChange }: { team: CompanyTeam; services: string[]; onChange: () => void }) {
  const [t, setT] = useState(team);
  const owns = new Set(t.owns);
  const toggle = (s: string) => setT({ ...t, owns: owns.has(s) ? t.owns.filter((x) => x !== s) : [...t.owns, s] });
  const setPerson = (i: number, patch: Partial<CompanyTeam["people"][number]>) =>
    setT({ ...t, people: t.people.map((p, k) => (k === i ? { ...p, ...patch } : patch.on_call ? { ...p, on_call: false } : p)) });
  return (
    <div className="rounded-xl border border-mist bg-white p-3">
      <input className="field w-full font-medium" aria-label="Team name" placeholder="Team name" value={t.name}
             onChange={(e) => setT({ ...t, name: e.target.value })} />
      <p className="kicker mt-3">Owns</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {services.map((s) => (
          <button key={s} onClick={() => toggle(s)} aria-pressed={owns.has(s)}
                  className={`rounded-full border px-2 py-0.5 text-xs ${owns.has(s) ? "border-plum/40 bg-lake/60 text-pine" : "border-mist muted hover:text-pine"}`}>
            {nameOf(s)}
          </button>
        ))}
      </div>
      <p className="kicker mt-3">People (one is on call)</p>
      {t.people.map((p, i) => (
        <div key={i} className="mt-1 flex items-center gap-2">
          <input className="field min-w-0 flex-1" aria-label="Name" placeholder="Name" value={p.name} onChange={(e) => setPerson(i, { name: e.target.value })} />
          <input className="field w-[38%]" aria-label="Contact" placeholder="#channel or email" value={p.contact ?? ""} onChange={(e) => setPerson(i, { contact: e.target.value })} />
          <label className="flex items-center gap-1 text-xs"><input type="radio" checked={!!p.on_call} onChange={() => setPerson(i, { on_call: true })} /> on call</label>
        </div>
      ))}
      <button className="mt-1 text-xs text-plum hover:underline" onClick={() => setT({ ...t, people: [...t.people, { id: "", name: "", on_call: false, contact: "" }] })}>+ person</button>
      <Saver onSave={() => api.saveCompany("team", t).then(onChange)}
             onDelete={team.id ? () => api.deleteCompany(team.id).then(onChange) : undefined} />
    </div>
  );
}

function RunbookCard({ rb, services, onChange }: { rb: CompanyRunbook; services: string[]; onChange: () => void }) {
  const [r, setR] = useState({ ...rb, stepsText: (rb.steps ?? []).join("\n") });
  return (
    <div className="rounded-xl border border-mist bg-white p-3">
      <div className="flex gap-2">
        <select className="field w-[40%]" aria-label="Service" value={r.service ?? ""} onChange={(e) => setR({ ...r, service: e.target.value })}>
          <option value="">service…</option>
          {services.map((s) => <option key={s} value={s}>{nameOf(s)}</option>)}
        </select>
        <input className="field min-w-0 flex-1" aria-label="Runbook title" placeholder="Title" value={r.title ?? ""} onChange={(e) => setR({ ...r, title: e.target.value })} />
      </div>
      <textarea className="field mt-2 h-16 w-full" aria-label="Steps" placeholder="One step per line" value={r.stepsText}
                onChange={(e) => setR({ ...r, stepsText: e.target.value })} />
      <p className="kicker mt-2">Automation (optional)</p>
      <div className="mt-1 flex gap-2">
        <input className="field min-w-0 flex-1 font-mono text-xs" aria-label="Automation URL" placeholder="https://your-ops-tool/hooks/…"
               value={r.automation_url ?? ""} onChange={(e) => setR({ ...r, automation_url: e.target.value })} />
        <select className="field" aria-label="Automation risk" value={r.automation_risk ?? "medium"} onChange={(e) => setR({ ...r, automation_risk: e.target.value })}>
          {["low", "medium", "high"].map((x) => <option key={x} value={x}>{x} risk</option>)}
        </select>
      </div>
      <Saver onSave={() => api.saveCompany("runbook", { ...r, steps: lines(r.stepsText) }).then(onChange)}
             onDelete={rb.id ? () => api.deleteCompany(rb.id).then(onChange) : undefined} />
    </div>
  );
}

export default function CompanySetup({ replay }: { replay: boolean }) {
  const [c, setC] = useState<Company | null>(null);
  const [version, setVersion] = useState(0);
  const [journey, setJourney] = useState({ name: "", routes: "" });
  const [msg, setMsg] = useState("");
  const load = () => api.company().then((x) => { setC(x); setVersion((v) => v + 1); }).catch((e) => setMsg(String(e.message ?? e)));
  useEffect(() => { load(); }, []);
  if (!c) return <p className="text-sm muted">{msg || "Loading your company…"}</p>;
  const blankTeam: CompanyTeam = { id: "", name: "", owns: [], people: [{ id: "", name: "", on_call: true, contact: "" }] };
  const blankRb: CompanyRunbook = { id: "", service: "", title: "", steps: [], automation_url: "", automation_risk: "medium" };
  return (
    <div className="space-y-6">
      <header>
        <h2 className="font-display text-3xl font-bold tracking-tight">Your company</h2>
        <p className="mt-1 max-w-[62ch] muted">RootCause finds the broken service from your telemetry on its own. This is the part only you
          know: who owns what, who is on call, which customer journeys matter and how your team fixes things.
          It is saved straight into the FalkorDB graph, so the next incident already uses it.</p>
        <ul className="mt-3 space-y-1 font-mono text-[11.5px] muted">
          <li>(:Team)-[:OWNS]-&gt;(:Service) &nbsp;→ who gets paged</li>
          <li>(:Journey)-[:REQUIRES]-&gt;(:Service) → business impact (journeys are found by route)</li>
          <li>(:Runbook)-[:FOR]-&gt;(:Service) &nbsp;→ steps and one-click automations, proposed with their risk</li>
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <a className="btn-ghost" href="/api/company/export" download="seed.yaml">Download as seed.yaml</a>
          <button className="btn-ghost" onClick={() => api.resetCompany().then(load).then(() => setMsg("back to config/seed.yaml"))}>Reset to seed</button>
          {msg && <span className="self-center text-xs muted">{msg}</span>}
        </div>
        {replay && <p className="mt-2 text-xs muted">Replay mode: automations are simulated, never called.</p>}
      </header>

      <section key={`t${version}`}>
        <h3 className="section-title">Teams and on call</h3>
        <div className="space-y-3">
          {c.teams.map((t) => <TeamCard key={t.id} team={t} services={c.services} onChange={load} />)}
          <details><summary className="cursor-pointer text-sm text-plum">+ Add a team</summary>
            <div className="mt-2"><TeamCard team={blankTeam} services={c.services} onChange={load} /></div></details>
        </div>
      </section>

      <section key={`j${version}`}>
        <h3 className="section-title">Customer journeys</h3>
        <table className="w-full text-sm">
          <tbody>
            {c.journeys.map((j) => (
              <tr key={j.id} className="border-t border-pine/10 align-top">
                <td className="w-[34%] whitespace-nowrap py-1.5 pr-3 font-medium">{j.name}</td>
                <td className="font-mono text-xs muted">{(j.routes ?? []).join("  ")}</td>
                <td className="text-right"><button className="text-xs muted hover:text-raspberry" onClick={() => api.deleteCompany(j.id).then(load)}>remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-2 flex gap-2">
          <input className="field w-[38%]" aria-label="Journey name" placeholder="e.g. Track order" value={journey.name} onChange={(e) => setJourney({ ...journey, name: e.target.value })} />
          <input className="field min-w-0 flex-1 font-mono text-xs" aria-label="Routes" placeholder="/api/orders, /orders" value={journey.routes} onChange={(e) => setJourney({ ...journey, routes: e.target.value })} />
        </div>
        <Saver onSave={() => api.saveCompany("journey", { name: journey.name, routes: lines(journey.routes) })
          .then(() => setJourney({ name: "", routes: "" })).then(load)} />
      </section>

      <section key={`r${version}`}>
        <h3 className="section-title">Runbooks and automations</h3>
        <div className="space-y-3">
          {c.runbooks.map((r) => <RunbookCard key={r.id} rb={r} services={c.services} onChange={load} />)}
          <details><summary className="cursor-pointer text-sm text-plum">+ Add a runbook</summary>
            <div className="mt-2"><RunbookCard rb={blankRb} services={c.services} onChange={load} /></div></details>
        </div>
      </section>
    </div>
  );
}
