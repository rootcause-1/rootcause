// The film's title card (bottom left, over the 3D stage). One sentence about the state of the system:
// learning / all quiet / "N alerts became 1 incident" (counts up when an incident forms) / fixed.
import { useEffect, useRef, useState } from "react";
import type { Graph, Incident, Status } from "../api";

function useCountUp(target: number): number {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setV(target); from.current = target; return; }
    let raf = 0;
    const a = from.current, t0 = performance.now();
    const tick = () => {
      const k = Math.min(1, (performance.now() - t0) / 900);
      const now = Math.round(a + (target - a) * (1 - Math.pow(1 - k, 3)));
      setV(now);
      from.current = now;
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return v;
}

const dur = (ms: number) => {
  const s = Math.round(ms / 1000);
  return s < 90 ? `${s} seconds` : `${Math.floor(s / 60)} min ${s % 60} s`;
};

export default function TitleCard({ status, graph, inc }: { status: Status | null; graph: Graph | null; inc: Incident | null }) {
  const alerts = inc?.alerts.length ?? 0;
  const shown = useCountUp(alerts);
  const services = graph?.nodes.filter((n) => n.labels.includes("Service")).length ?? 0;
  const calls = Math.round((graph?.edges ?? []).filter((e) => e.type === "CALLS").reduce((s, e) => s + (e.rps ?? 0), 0));
  const learning = status && status.learning_left_ms > 0;
  const root = inc?.root_target?.replace(/^edge:/, "");
  const conf = inc?.hypotheses?.[0]?.score;
  const fix = inc?.actions?.find((a) => a.status === "verified" || a.status === "executed");

  let body;
  if (!status || !graph) {
    body = <h2 className="font-display text-[clamp(44px,5vw,76px)] font-bold leading-[0.92] tracking-[-0.03em] text-pine/40">Connecting…</h2>;
  } else if (inc && inc.status === "open") {
    body = (
      <>
        <h2 className="font-display text-[clamp(56px,7vw,104px)] font-bold leading-[0.88] tracking-[-0.035em]">
          <span className="text-saffron">{shown}</span> alerts<br />
          became <span className="text-raspberry">1</span> incident
        </h2>
        <p className="mt-4 max-w-[34ch] text-lg leading-snug text-pine">
          {root ? <>The cause is <b className="text-raspberry">{root}</b>{conf ? `, ranked first with a score of ${conf.toFixed(2)}.` : "."}</>
                : "Ranking the causes…"}
        </p>
      </>
    );
  } else if (inc && inc.status === "resolved" && inc.resolved_ts && Date.now() - inc.resolved_ts < 5 * 60_000) {
    body = (
      <>
        <h2 className="font-display text-[clamp(56px,7vw,104px)] font-bold leading-[0.88] tracking-[-0.035em]">Fixed.</h2>
        <p className="mt-4 max-w-[36ch] text-lg leading-snug">
          {inc.root_target} recovered{inc.ttr_ms ? ` ${dur(inc.ttr_ms)} after the first alert` : ""}
          {fix ? `, after ${fix.kind.replace("_", " ")} of ${fix.target}.` : "."}
        </p>
      </>
    );
  } else if (learning) {
    body = (
      <>
        <h2 className="font-display text-[clamp(44px,5vw,76px)] font-bold leading-[0.92] tracking-[-0.03em]">Learning what<br />normal looks like</h2>
        <p className="mt-4 text-lg">{Math.ceil(status!.learning_left_ms / 1000)} seconds of healthy traffic to go.</p>
      </>
    );
  } else {
    body = (
      <>
        <h2 className="font-display text-[clamp(56px,7vw,104px)] font-bold leading-[0.88] tracking-[-0.035em]">All quiet.</h2>
        <p className="mt-4 max-w-[34ch] text-lg leading-snug">
          {services} services carrying {calls} calls a second. RootCause is watching every one of them.
        </p>
      </>
    );
  }
  return <div className="pointer-events-none select-none text-pine" aria-live="polite">{body}</div>;
}
