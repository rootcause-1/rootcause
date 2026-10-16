// Layered 3D layout for the service graph, laid out like a diorama on a table:
// x = tier (callers on the left, dependencies to the right), z = fan-out within a tier, y = height above the ground.
// Positions only change when the topology changes, so live metric updates never make the scene jump.
import type { Graph } from "../api";

export type P3 = [number, number, number];

const FLOW = new Set(["CALLS", "USES", "PRODUCES_TO", "CONSUMED_BY"]);

export function topologyKey(g: Graph): string {
  const ids = g.nodes.map((n) => n.id).sort().join(",");
  const es = g.edges.filter((e) => FLOW.has(e.type)).map((e) => `${e.source}>${e.target}`).sort().join(",");
  return `${ids}|${es}`;
}

export function layout(g: Graph): Record<string, P3> {
  const ids = new Set(g.nodes.map((n) => n.id));
  const edges = g.edges.filter((e) => FLOW.has(e.type) && ids.has(e.source) && ids.has(e.target) && e.source !== e.target);
  const preds: Record<string, string[]> = {};
  for (const id of ids) preds[id] = [];
  for (const e of edges) preds[e.target].push(e.source);

  // tier = longest path from a source (bounded, so cycles cannot loop forever)
  const tier: Record<string, number> = {};
  for (const id of ids) tier[id] = 0;
  for (let pass = 0; pass < ids.size; pass++) {
    let moved = false;
    for (const e of edges) {
      if (tier[e.target] < tier[e.source] + 1 && tier[e.source] + 1 < 12) {
        tier[e.target] = tier[e.source] + 1;
        moved = true;
      }
    }
    if (!moved) break;
  }

  const tiers: string[][] = [];
  for (const id of [...ids].sort()) (tiers[tier[id]] ??= []).push(id);
  // two barycentre sweeps: order each tier by the mean position of its callers, to keep edges short
  const order: Record<string, number> = {};
  tiers.forEach((t) => t.forEach((id, i) => (order[id] = i - (t.length - 1) / 2)));
  for (let sweep = 0; sweep < 2; sweep++) {
    for (const t of tiers) {
      if (!t) continue;
      const bary = (id: string) => {
        const p = preds[id].filter((x) => order[x] !== undefined);
        return p.length ? p.reduce((s, x) => s + order[x], 0) / p.length : order[id];
      };
      t.sort((a, b) => bary(a) - bary(b));
      t.forEach((id, i) => (order[id] = i - (t.length - 1) / 2));
    }
  }

  const pos: Record<string, P3> = {};
  const nt = tiers.length;
  tiers.forEach((t, ti) => {
    if (!t) return;
    t.forEach((id, i) => {
      const z = (i - (t.length - 1) / 2) * 2.4;
      const x = (ti - (nt - 1) / 2) * 4.4 + Math.sin(i * 1.7) * 0.35;
      const y = 1.1 + 0.35 * Math.cos(ti * 0.9 + i * 1.3); // a gentle rolling surface, not a flat grid
      pos[id] = [x, y, z];
    });
  });
  return pos;
}

/** A soft arc between two points (lifted towards the camera), sampled for lines and particles. */
export function arc(a: P3, b: P3, lift = 0.9): (t: number) => P3 {
  const mid: P3 = [(a[0] + b[0]) / 2, Math.max(a[1], b[1]) + lift, (a[2] + b[2]) / 2];
  return (t: number) => {
    const u = 1 - t;
    return [
      u * u * a[0] + 2 * u * t * mid[0] + t * t * b[0],
      u * u * a[1] + 2 * u * t * mid[1] + t * t * b[1],
      u * u * a[2] + 2 * u * t * mid[2] + t * t * b[2],
    ];
  };
}
