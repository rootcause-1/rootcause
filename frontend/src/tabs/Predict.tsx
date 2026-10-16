// Predict: "what if this breaks?" — the predicted blast radius is ringed in the 3D scene (plum); after the break,
// score the prediction against what actually went anomalous.
import { useState } from "react";
import type { Graph } from "../api";
import { api, pct } from "../api";

export default function Predict({ graph, onOverlay }: { graph: Graph | null; onOverlay: (ids: string[]) => void }) {
  const [node, setNode] = useState("");
  const [pred, setPred] = useState<{ id: string; services: string[]; queues: string[]; journeys: string[] } | null>(null);
  const [score, setScore] = useState<{ precision: number; recall: number; actual: string[] } | null>(null);
  const services = (graph?.nodes ?? []).filter((n) => n.labels.includes("Service")).map((n) => n.id).sort();

  async function predict() {
    const p = await api.predict(node);
    setPred(p); setScore(null);
    onOverlay([...p.services, ...p.queues]);
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="font-display text-3xl font-bold tracking-tight">What if this breaks?</h2>
        <p className="mt-1 max-w-[60ch] muted">RootCause walks the graph upstream from a service to predict who else fails.
          Break it afterwards to check the prediction.</p>
      </header>
      <div className="flex items-center gap-2">
        <select className="field" value={node} onChange={(e) => setNode(e.target.value)} aria-label="Service to break">
          <option value="">Pick a service…</option>
          {services.map((s) => <option key={s}>{s}</option>)}
        </select>
        <button className="btn-primary" disabled={!node} onClick={predict}>Predict</button>
      </div>
      {pred && (
        <section className="space-y-2 text-[15px]">
          <p><b className="font-display text-2xl text-plum">{pred.services.length}</b> services would fail: {pred.services.join(", ")}.</p>
          <p><b className="font-display text-2xl text-plum">{pred.queues.length}</b> queues would lag{pred.queues.length ? `: ${pred.queues.join(", ")}` : ""}.</p>
          <p><b className="font-display text-2xl text-plum">{pred.journeys.length}</b> journeys would break{pred.journeys.length ? `: ${pred.journeys.map((j) => j.replace("journey:", "")).join(", ")}` : ""}.</p>
          <p className="text-sm muted">They are ringed in plum on the graph. Break the service in the Chaos lab, wait for the alerts, then score.</p>
          <button className="btn-ghost" onClick={async () => setScore(await api.scorePrediction(pred.id))}>Score against what happened</button>
        </section>
      )}
      {score && (
        <section>
          <h3 className="section-title">Prediction against reality</h3>
          <p className="font-display text-4xl font-bold">{pct(score.precision)} precise, {pct(score.recall)} complete</p>
          <p className="mt-1 text-sm muted">Actually alerting: {score.actual.join(", ") || "nothing yet"}.</p>
        </section>
      )}
    </div>
  );
}
