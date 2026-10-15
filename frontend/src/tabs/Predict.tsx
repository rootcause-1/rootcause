// Predict: what-if on a node (dashed overlay on the graph), then score precision/recall after the break.
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
    <div className="grid grid-cols-2 gap-4 p-4">
      <div className="card space-y-3">
        <div className="label">What if this breaks?</div>
        <select className="w-full rounded border border-slate-700 bg-slate-950 p-1.5 text-sm" value={node}
                onChange={(e) => setNode(e.target.value)}>
          <option value="">pick a service…</option>
          {services.map((s) => <option key={s}>{s}</option>)}
        </select>
        <button className="btn-primary" disabled={!node} onClick={predict}>Predict</button>
        {pred && (
          <div className="text-sm">
            <p><b>{pred.services.length}</b> services fail: <span className="font-mono">{pred.services.join(", ")}</span></p>
            <p><b>{pred.queues.length}</b> queues lag: <span className="font-mono">{pred.queues.join(", ") || "-"}</span></p>
            <p><b>{pred.journeys.length}</b> journeys break: {pred.journeys.map((j) => j.replace("journey:", "")).join(", ") || "-"}</p>
            <p className="mt-2 text-xs text-slate-400">Now break it in the Chaos lab, wait for alerts, then score the prediction.</p>
            <button className="btn-ghost mt-2" onClick={async () => setScore(await api.scorePrediction(pred.id))}>Score vs reality</button>
          </div>
        )}
      </div>
      {score && (
        <div className="card">
          <div className="label mb-2">Prediction vs :Anomalous</div>
          <p className="text-3xl font-bold">precision {pct(score.precision)} · recall {pct(score.recall)}</p>
          <p className="mt-2 text-sm">actually anomalous: <span className="font-mono">{score.actual.join(", ") || "-"}</span></p>
        </div>
      )}
    </div>
  );
}
