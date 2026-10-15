// Live service graph: Cytoscape + dagre, left -> right (edge -> core -> data/queues).
// Edge colour by error rate, width by traffic; :Anomalous nodes pulse; overlays for evidence path,
// prediction (dashed), blast radius (halo) and the nodes an agent step cited.
import cytoscape, { Core } from "cytoscape";
import dagre from "cytoscape-dagre";
import { useEffect, useRef } from "react";
import type { Graph } from "../api";

cytoscape.use(dagre);

export type Overlays = { path?: string[]; predicted?: string[]; blast?: string[]; cited?: string[] };

const errColour = (e?: number | null) => (e == null ? "#475569" : e >= 0.05 ? "#ef4444" : e >= 0.01 ? "#f59e0b" : "#22c55e");

// cast: @types/cytoscape lacks the underlay-* properties Cytoscape 3.30 supports
const style = [
  { selector: "node", style: {
      label: "data(label)", color: "#e2e8f0", "font-size": 11, "text-valign": "bottom", "text-margin-y": 4,
      "background-color": "#334155", width: 26, height: 26, "border-width": 2, "border-color": "#64748b" } },
  { selector: "node.Queue", style: { shape: "round-rectangle", "background-color": "#1e3a8a" } },
  { selector: "node.Datastore", style: { shape: "barrel", "background-color": "#3b0764" } },
  { selector: "node.anomalous", style: { "border-color": "#ef4444", "border-width": 4, "background-color": "#7f1d1d" } },
  { selector: "node.anomalous.pulse", style: { "border-width": 9, "border-opacity": 0.5 } },
  { selector: "node.blast", style: { "underlay-color": "#f59e0b", "underlay-opacity": 0.25, "underlay-padding": 10 } },
  { selector: "node.predicted", style: { "border-style": "dashed", "border-color": "#a78bfa", "border-width": 4 } },
  { selector: "node.onpath", style: { "background-color": "#facc15", "border-color": "#fde047" } },
  { selector: "node.cited", style: { "underlay-color": "#38bdf8", "underlay-opacity": 0.45, "underlay-padding": 8 } },
  { selector: "edge", style: {
      "curve-style": "bezier", "target-arrow-shape": "triangle", "line-color": "data(colour)",
      "target-arrow-color": "data(colour)", width: "data(width)", opacity: 0.85 } },
  { selector: "edge.PRODUCES_TO, edge.CONSUMED_BY", style: { "line-style": "dotted" } },
  { selector: "edge.BLAMES", style: { "line-color": "#f43f5e", "target-arrow-color": "#f43f5e", width: 1.5,
      "line-style": "dashed", "curve-style": "unbundled-bezier", opacity: 0.6 } },
  { selector: "edge.onpath", style: { "line-color": "#facc15", "target-arrow-color": "#facc15", width: 5,
      "line-dash-pattern": [8, 4], "line-style": "dashed" } },
] as unknown as cytoscape.Stylesheet[];

export default function GraphView({ graph, overlays }: { graph: Graph | null; overlays: Overlays }) {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const shape = useRef("");

  useEffect(() => {
    if (!box.current) return;
    cy.current = cytoscape({ container: box.current, style, wheelSensitivity: 0.2 });
    (window as unknown as { __cy?: Core }).__cy = cy.current; // debugging handle
    const t = setInterval(() => cy.current?.nodes(".anomalous").toggleClass("pulse"), 700);
    // the panel changes size between tabs (full height on Incident, 45vh elsewhere): keep the canvas in sync
    const ro = new ResizeObserver(() => { cy.current?.resize(); cy.current?.fit(undefined, 30); });
    ro.observe(box.current);
    return () => { clearInterval(t); ro.disconnect(); cy.current?.destroy(); };
  }, []);

  useEffect(() => {
    const c = cy.current;
    if (!c || !graph) return;
    const ids = new Set(graph.nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    const key = graph.nodes.map((n) => n.id).sort().join() + "|" +
      edges.filter((e) => e.type !== "BLAMES").map((e) => `${e.source}>${e.target}`).sort().join();
    // every update rebuilds the elements; keep each node where it was so only topology changes re-layout
    const pos: Record<string, cytoscape.Position> = {};
    c.nodes().forEach((n) => { pos[n.id()] = { ...n.position() }; });
    c.batch(() => {
      c.elements().remove();
      c.add(graph.nodes.map((n) => ({
        group: "nodes" as const,
        position: pos[n.id] ? { ...pos[n.id] } : undefined,
        data: { id: n.id, label: n.id.replace(/^(queue|db|cache):/, "") },
        classes: [...n.labels, n.labels.includes("Anomalous") ? "anomalous" : ""].join(" "),
      })));
      c.add(edges.map((e, i) => ({
        group: "edges" as const,
        data: { id: `${e.type}-${i}-${e.source}-${e.target}`, source: e.source, target: e.target,
                colour: errColour(e.err_rate), width: Math.min(8, 1 + Math.log2(1 + (e.rps ?? e.rate ?? 0) * 4)) },
        classes: e.type,
      })));
    });
    if (key !== shape.current) {
      shape.current = key;
      // BLAMES edges are transient: lay out on the stable topology only
      c.elements().not(c.edges(".BLAMES"))
        .layout({ name: "dagre", rankDir: "LR", nodeSep: 25, rankSep: 90 } as cytoscape.LayoutOptions).run();
    }
  }, [graph]);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.elements().removeClass("onpath predicted blast cited");
    const mark = (ids: string[] | undefined, cls: string) => ids?.forEach((id) => c.getElementById(id).addClass(cls));
    mark(overlays.predicted, "predicted");
    mark(overlays.blast, "blast");
    mark(overlays.cited, "cited");
    const p = overlays.path ?? [];
    mark(p, "onpath");
    for (let i = 0; i + 1 < p.length; i++) {
      c.edges(`[source = "${p[i]}"][target = "${p[i + 1]}"]`).not(".BLAMES").addClass("onpath");
    }
  }, [overlays, graph]);

  return <div ref={box} className="h-full w-full" />;
}
