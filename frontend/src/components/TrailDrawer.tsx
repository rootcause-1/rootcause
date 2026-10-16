// The agent's investigation, in order (each (:Step) in the graph). Hovering a step rings the nodes it cited
// on the service map.
import type { Step } from "../api";
import { clock } from "../api";

export default function TrailDrawer({ steps, onHover }: { steps: Step[]; onHover: (ids: string[]) => void }) {
  if (steps.length === 0) return <p className="text-sm muted">No steps yet.</p>;
  return (
    <ol className="relative space-y-0.5 border-l border-pine/15 pl-4">
      {steps.map((s) => (
        <li key={s.id} className="relative cursor-default rounded-lg px-2 py-1.5 hover:bg-pine/5"
            onMouseEnter={() => onHover(s.cited)} onMouseLeave={() => onHover([])}
            onFocus={() => onHover(s.cited)} onBlur={() => onHover([])} tabIndex={0}>
          <span className="absolute -left-[21px] top-3 h-2 w-2 rounded-full bg-pine" aria-hidden />
          <div className="flex justify-between text-xs muted">
            <span className="font-semibold text-pine">{s.tool.replace(/_/g, " ")}</span><span>{clock(s.ts)}</span>
          </div>
          <div className="text-sm">{s.summary}</div>
        </li>
      ))}
    </ol>
  );
}
