// Agent trail: the incident's (:Step) chain. Hovering a step highlights the nodes it cited on the graph.
import type { Step } from "../api";
import { clock } from "../api";

export default function TrailDrawer({ steps, onHover }: { steps: Step[]; onHover: (ids: string[]) => void }) {
  return (
    <div className="card h-full overflow-y-auto">
      <div className="label mb-2">Agent trail</div>
      {steps.length === 0 && <p className="text-sm text-slate-400">no steps yet</p>}
      <ol className="space-y-1.5">
        {steps.map((s) => (
          <li key={s.id} className="cursor-default rounded px-2 py-1 hover:bg-slate-800"
              onMouseEnter={() => onHover(s.cited)} onMouseLeave={() => onHover([])}>
            <div className="flex justify-between text-xs text-slate-400">
              <span>{s.n}. <span className="font-mono text-sky-300">{s.tool}</span></span><span>{clock(s.ts)}</span>
            </div>
            <div className="text-sm">{s.summary}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}
