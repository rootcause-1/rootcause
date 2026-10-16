// The 3D stage: the live service graph as a diorama on a table (Three.js via react-three-fiber).
//
// What you see is data, not decoration:
// - each glossy node is a service / queue / datastore; its size follows its request rate;
// - particles travel along each call edge at a rate that follows its request rate; the share of raspberry
//   particles is the edge's error rate;
// - alerting (:Anomalous) nodes turn saffron and send out a shockwave; dashed raspberry arcs are BLAMES edges;
// - the root cause gets a raspberry beacon, and a light pulse runs down the evidence path towards it;
// - "Director" moves the camera with the incident (overview -> the root cause -> back to overview when it heals).
import { ContactShadows, Grid, Html, Line, OrbitControls, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { Graph, GraphEdge, GraphNode } from "../api";
import { arc, layout, topologyKey, type P3 } from "./layout";
import { C } from "./palette";

export type Focus = { root?: string | null; path?: string[]; cited?: string[]; predicted?: string[] };
type Props = {
  graph: Graph | null; focus: Focus; director: boolean; incidentOpen: boolean;
  picked: string | null; onPick: (id: string | null) => void;
  frame?: number; // 1: panels on the right, keep the action left of centre; -1: panels on the left; 0: centred
};

const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const FLOW = new Set(["CALLS", "USES", "PRODUCES_TO", "CONSUMED_BY"]);
const easeOut = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

function rootNode(root?: string | null): string | null {
  if (!root) return null;
  return root.startsWith("edge:") ? root.split("->")[1] : root;
}

export default function Stage(props: Props) {
  return (
    <Canvas camera={{ position: [0, 13, 24], fov: 38 }} dpr={[1, 2]} gl={{ antialias: true }}
            onPointerMissed={() => props.onPick(null)}>
      <color attach="background" args={[C.porcelain]} />
      <fog attach="fog" args={[C.porcelain, 30, 70]} />
      <hemisphereLight args={["#ffffff", "#dfe6dc", 1.1]} />
      <directionalLight position={[8, 14, 10]} intensity={1.6} />
      <directionalLight position={[-10, 6, -6]} intensity={0.45} color="#fff4e0" />
      <Scene {...props} />
    </Canvas>
  );
}

function Scene({ graph, focus, director, incidentOpen, picked, onPick, frame = 1 }: Props) {
  const key = graph ? topologyKey(graph) : "";
  const pos = useMemo(() => (graph ? layout(graph) : {}), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const start = useRef(performance.now());
  const hadNodes = useRef(false);
  useEffect(() => { // the intro (tiers rising from the table) starts when the first graph arrives
    if (!hadNodes.current && graph && graph.nodes.length > 0) { hadNodes.current = true; start.current = performance.now(); }
  }, [graph]);
  const [hover, setHover] = useState<string | null>(null);
  const root = rootNode(focus.root);
  // when the root cause goes away (fixed), send a healing wave out from where it was
  const lastRoot = useRef<string | null>(null);
  const [heal, setHeal] = useState<{ at: P3; key: number } | null>(null);
  useEffect(() => {
    if (lastRoot.current && !root && pos[lastRoot.current]) setHeal({ at: pos[lastRoot.current], key: performance.now() });
    lastRoot.current = root;
  }, [root]); // eslint-disable-line react-hooks/exhaustive-deps
  const rootEdge = focus.root?.startsWith("edge:") ? focus.root.slice(5) : null;
  const nodes = graph?.nodes.filter((n) => pos[n.id]) ?? [];
  const tierOf = (p: P3) => p[0];
  const minX = Math.min(...nodes.map((n) => tierOf(pos[n.id])), 0);
  const flows = (graph?.edges ?? []).filter((e) => FLOW.has(e.type) && pos[e.source] && pos[e.target]);
  const blames = (graph?.edges ?? []).filter((e) => e.type === "BLAMES" && pos[e.source] && pos[e.target]);

  return (
    <>
      <Ground />
      <ContactShadows position={[0, 0.01, 0]} opacity={0.32} scale={60} blur={2.6} far={6} color={C.pine} />
      {flows.map((e) => (
        <Edge key={`${e.type}${e.source}${e.target}`} e={e} a={pos[e.source]} b={pos[e.target]} start={start}
              dim={incidentOpen && !onEdgePath(e, focus.path)} highlight={rootEdge === `${e.source}->${e.target}`} />
      ))}
      <Particles edges={flows} pos={pos} start={start}
                 quiet={incidentOpen ? (e) => !onEdgePath(e, focus.path) && !anomalousEdge(e, graph) : undefined} />
      {blames.map((e) => <BlameArc key={`b${e.source}${e.target}`} a={pos[e.source]} b={pos[e.target]} />)}
      {focus.path && focus.path.length > 1 && <EvidencePulse path={focus.path} pos={pos} />}
      {nodes.map((n) => (
        <Node key={n.id} n={n} p={pos[n.id]} start={start} delay={(tierOf(pos[n.id]) - minX) / 4.4 * 0.16}
              isRoot={root === n.id} onPath={!!focus.path?.includes(n.id)}
              cited={!!focus.cited?.includes(n.id)} predicted={!!focus.predicted?.includes(n.id)}
              dim={incidentOpen && !n.labels.includes("Anomalous") && !focus.path?.includes(n.id)}
              hovered={hover === n.id} picked={picked === n.id}
              onHover={setHover} onPick={onPick} />
      ))}
      {heal && !reduced && <HealWave key={heal.key} at={heal.at} onDone={() => setHeal(null)} />}
      <Director pos={pos} focusIds={picked ? [picked] : root ? [...(focus.path ?? []), root] : []} director={director} frame={frame} />
    </>
  );
}

function anomalousEdge(e: GraphEdge, g: Graph | null) {
  const hot = (id: string) => !!g?.nodes.find((n) => n.id === id)?.labels.includes("Anomalous");
  return hot(e.source) && hot(e.target);
}

function onEdgePath(e: GraphEdge, path?: string[]) {
  if (!path) return false;
  const i = path.indexOf(e.source);
  return i >= 0 && path[i + 1] === e.target;
}

// ---------------------------------------------------------------------------------------------- ground
function Ground() {
  return (
    <>
      <mesh rotation-x={-Math.PI / 2} position={[0, 0, 0]}>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color={C.porcelain} roughness={1} />
      </mesh>
      <Grid position={[0, 0.005, 0]} args={[120, 120]} cellSize={1.1} cellThickness={0.5} cellColor="#d9dfd5"
            sectionSize={4.4} sectionThickness={0.9} sectionColor="#c9d3c6" fadeDistance={55} fadeStrength={1.4}
            infiniteGrid />
    </>
  );
}

// ---------------------------------------------------------------------------------------------- nodes
type NodeProps = {
  n: GraphNode; p: P3; start: React.MutableRefObject<number>; delay: number; isRoot: boolean; onPath: boolean;
  cited: boolean; predicted: boolean; dim: boolean; hovered: boolean; picked: boolean;
  onHover: (id: string | null) => void; onPick: (id: string) => void;
};

function Node({ n, p, start, delay, isRoot, onPath, cited, predicted, dim, hovered, picked, onHover, onPick }: NodeProps) {
  const group = useRef<THREE.Group>(null); // position (effects hang off this, unscaled)
  const body = useRef<THREE.Group>(null);  // scale (the node itself)
  const mat = useRef<THREE.MeshPhysicalMaterial>(null);
  const anomalous = n.labels.includes("Anomalous");
  const kind = n.labels.includes("Queue") ? "queue" : n.labels.includes("Datastore") ? "store" : "service";
  const size = 0.34 + 0.11 * Math.log10(1 + (n.rps ?? 0) * 4);
  const target = useMemo(() => new THREE.Color(
    isRoot ? C.raspberry : anomalous ? C.saffron : dim ? "#CFE0D4" : kind === "service" ? C.eucalyptus : "#8FB9A3"), [isRoot, anomalous, dim, kind]);

  useFrame((state, dt) => {
    const g = group.current;
    if (!g || !body.current || !mat.current) return;
    const t = (performance.now() - start.current) / 1000 - delay;
    const rise = reduced ? 1 : easeOut(t / 1.1);
    const bob = reduced ? 0 : Math.sin(state.clock.elapsedTime * 1.3 + p[2]) * 0.05;
    g.position.lerp(new THREE.Vector3(p[0], p[1] * rise - (1 - rise) * 0.8 + bob, p[2]), 1 - Math.exp(-dt * 6));
    const pulse = anomalous && !reduced ? 1 + Math.sin(state.clock.elapsedTime * 5) * 0.06 : 1;
    const s = Math.max(0.001, rise) * pulse * (hovered || picked ? 1.18 : 1) * (isRoot ? 1.25 : 1);
    body.current.scale.lerp(new THREE.Vector3(s, s, s), 1 - Math.exp(-dt * 8));
    mat.current.color.lerp(target, 1 - Math.exp(-dt * 3));
    mat.current.opacity += ((dim ? 0.42 : 1) - mat.current.opacity) * (1 - Math.exp(-dt * 3));
    mat.current.emissive.copy(mat.current.color).multiplyScalar(isRoot ? 0.35 : anomalous ? 0.18 : 0.02);
  });

  const material = <meshPhysicalMaterial ref={mat} color={C.eucalyptus} roughness={0.28} clearcoat={1} transparent
                                         clearcoatRoughness={0.15} metalness={0.05} />;
  const events = {
    onPointerOver: (e: { stopPropagation: () => void }) => { e.stopPropagation(); onHover(n.id); document.body.style.cursor = "pointer"; },
    onPointerOut: () => { onHover(null); document.body.style.cursor = ""; },
    onClick: (e: { stopPropagation: () => void }) => { e.stopPropagation(); onPick(n.id); },
  };
  return (
    <group ref={group} position={[p[0], -1, p[2]]}>
      <group ref={body} scale={0.001}>
        {kind === "service" && <mesh {...events}><sphereGeometry args={[size, 48, 32]} />{material}</mesh>}
        {kind === "queue" && <RoundedBox {...events} args={[size * 2.6, size * 1.1, size * 1.4]} radius={0.12} smoothness={4}>{material}</RoundedBox>}
        {kind === "store" && <mesh {...events}><cylinderGeometry args={[size, size, size * 1.5, 40]} />{material}</mesh>}
      </group>
      {anomalous && !reduced && <Shockwave colour={isRoot ? C.raspberry : C.saffron} height={p[1]} />}
      {isRoot && <Beacon height={p[1]} />}
      {(cited || predicted || onPath) && <Halo colour={predicted ? C.plum : cited ? C.pine : C.saffron} size={size} />}
      {(!dim || hovered || picked || cited) && (
        <Html position={[0, size + 0.45, 0]} center zIndexRange={[5, 0]} style={{ pointerEvents: "none" }}>
          <div className={`node-label ${isRoot ? "is-root" : anomalous ? "is-hot" : ""}`}>
            {n.id.replace(/^(queue|db|cache):/, "")}
          </div>
        </Html>
      )}
      {(hovered || picked) && (
        <Html position={[size + 0.4, 0.2, 0]} zIndexRange={[8, 6]} style={{ pointerEvents: "none" }}>
          <div className="node-card">
            <b>{n.id}</b>
            <span>{fmt(n.rps, " req/s")}</span>
            <span>{n.err_rate != null ? `${(n.err_rate * 100).toFixed(1)} % errors` : "no errors"}</span>
            {n.p95_ms != null && <span>p95 {Math.round(n.p95_ms)} ms</span>}
            {n.lag != null && <span>lag {Math.round(n.lag)}</span>}
          </div>
        </Html>
      )}
    </group>
  );
}

const fmt = (v: number | null | undefined, unit: string) => (v == null ? "–" : `${v < 10 ? v.toFixed(2) : Math.round(v)}${unit}`);

function Shockwave({ colour, height }: { colour: string; height: number }) {
  const ring = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    const r = ring.current;
    if (!r) return;
    const t = (state.clock.elapsedTime % 1.8) / 1.8;
    r.scale.setScalar(0.6 + t * 3.2);
    (r.material as THREE.MeshBasicMaterial).opacity = 0.55 * (1 - t);
  });
  return (
    <mesh ref={ring} rotation-x={-Math.PI / 2} position={[0, -height + 0.03, 0]}>
      <ringGeometry args={[0.55, 0.62, 64]} />
      <meshBasicMaterial color={colour} transparent depthWrite={false} />
    </mesh>
  );
}

function Beacon({ height }: { height: number }) {
  const halo = useRef<THREE.Mesh>(null);
  useFrame((state, dt) => { if (halo.current) halo.current.rotation.z += dt * 0.8; });
  return (
    <>
      <mesh position={[0, 3.2 - height / 2, 0]}>
        <cylinderGeometry args={[0.02, 0.07, 6.4 + height, 16, 1, true]} />
        <meshBasicMaterial color={C.raspberry} transparent opacity={0.16} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={halo} rotation-x={Math.PI / 2}>
        <torusGeometry args={[0.85, 0.025, 12, 96]} />
        <meshBasicMaterial color={C.raspberry} />
      </mesh>
    </>
  );
}

function Halo({ colour, size }: { colour: string; size: number }) {
  return (
    <mesh rotation-x={Math.PI / 2}>
      <torusGeometry args={[size + 0.28, 0.03, 10, 72]} />
      <meshBasicMaterial color={colour} transparent opacity={0.85} />
    </mesh>
  );
}

// ---------------------------------------------------------------------------------------------- edges
function Edge({ e, a, b, start, dim, highlight }: { e: GraphEdge; a: P3; b: P3; start: React.MutableRefObject<number>; dim: boolean; highlight: boolean }) {
  const ref = useRef<{ material: { opacity: number } }>(null);
  const curve = useMemo(() => arc(a, b, 0.35 + 0.08 * Math.hypot(b[0] - a[0], b[2] - a[2])), [a, b]);
  const pts = useMemo(() => Array.from({ length: 28 }, (_, i) => curve(i / 27)), [curve]);
  const err = e.err_rate ?? 0;
  const colour = highlight ? C.raspberry : err >= 0.05 ? C.raspberry : err >= 0.01 ? C.saffron : "#b9d3c2";
  const width = highlight ? 4 : 1 + Math.min(3, Math.log2(1 + (e.rps ?? e.rate ?? 0) * 3));
  const async = e.type === "PRODUCES_TO" || e.type === "CONSUMED_BY";
  useFrame(() => {
    const t = (performance.now() - start.current) / 1000;
    if (ref.current) ref.current.material.opacity = (reduced ? 1 : easeOut((t - 0.8) / 1.2)) * (dim ? 0.35 : 0.9);
  });
  return <Line ref={ref as never} points={pts} color={colour} lineWidth={width} transparent dashed={async}
               dashSize={0.25} gapSize={0.18} />;
}

function BlameArc({ a, b }: { a: P3; b: P3 }) {
  const ref = useRef<{ material: { dashOffset: number } }>(null);
  const pts = useMemo(() => { const c = arc(a, b, 2.4); return Array.from({ length: 40 }, (_, i) => c(i / 39)); }, [a, b]);
  useFrame((_, dt) => { if (ref.current && !reduced) ref.current.material.dashOffset -= dt * 1.4; });
  return <Line ref={ref as never} points={pts} color={C.raspberry} lineWidth={1.6} dashed dashSize={0.3} gapSize={0.22}
               transparent opacity={0.7} />;
}

const MAX_PARTICLES = 420;

function Particles({ edges, pos, start, quiet }: {
  edges: GraphEdge[]; pos: Record<string, P3>; start: React.MutableRefObject<number>; quiet?: (e: GraphEdge) => boolean;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const tmp = useMemo(() => new THREE.Object3D(), []);
  // particles per edge follow its request rate; a share of them (the error rate) are raspberry
  const plan = useMemo(() => {
    const out: { curve: (t: number) => P3; phase: number; speed: number; bad: boolean; calm: boolean }[] = [];
    for (const e of edges) {
      const a = pos[e.source], b = pos[e.target];
      const rate = e.rps ?? e.rate ?? 0;
      const k = rate <= 0 ? 0 : Math.min(14, Math.max(1, Math.round(1 + Math.log2(1 + rate * 4) * 2)));
      const curve = arc(a, b, 0.35 + 0.08 * Math.hypot(b[0] - a[0], b[2] - a[2]));
      const calm = !!quiet?.(e);
      for (let i = 0; i < k && out.length < MAX_PARTICLES; i++) {
        out.push({ curve, phase: i / k, speed: 0.22 + Math.min(0.35, rate * 0.02), bad: i / k < (e.err_rate ?? 0), calm });
      }
    }
    return out;
  }, [edges, pos, quiet]);
  const colours = useMemo(() => {
    const good = new THREE.Color(C.eucalyptus), bad = new THREE.Color(C.raspberry), pale = new THREE.Color("#D3E2D7");
    return plan.map((p) => (p.calm ? pale : p.bad ? bad : good));
  }, [plan]);

  useEffect(() => {
    const m = mesh.current;
    if (!m) return;
    colours.forEach((c, i) => m.setColorAt(i, c));
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [colours]);

  useFrame((state) => {
    const m = mesh.current;
    if (!m) return;
    const intro = easeOut(((performance.now() - start.current) / 1000 - 1.6) / 1);
    const time = reduced ? 0 : state.clock.elapsedTime;
    plan.forEach((p, i) => {
      const t = (p.phase + time * p.speed) % 1;
      const [x, y, z] = p.curve(t);
      tmp.position.set(x, y, z);
      tmp.scale.setScalar(intro * (p.calm ? 0.045 : p.bad ? 0.11 : 0.075));
      tmp.updateMatrix();
      m.setMatrixAt(i, tmp.matrix);
    });
    m.count = plan.length;
    m.instanceMatrix.needsUpdate = true;
  });
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, MAX_PARTICLES]}>
      <sphereGeometry args={[1, 12, 8]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}

// ---------------------------------------------------------------------------------------------- evidence pulse
function EvidencePulse({ path, pos }: { path: string[]; pos: Record<string, P3> }) {
  const ball = useRef<THREE.Mesh>(null);
  const trail = useRef<THREE.Mesh>(null);
  const segs = useMemo(() => {
    const s: ((t: number) => P3)[] = [];
    for (let i = 0; i + 1 < path.length; i++) {
      const a = pos[path[i]], b = pos[path[i + 1]];
      if (a && b) s.push(arc(a, b, 0.35 + 0.08 * Math.hypot(b[0] - a[0], b[2] - a[2])));
    }
    return s;
  }, [path, pos]);
  const pts = useMemo(() => segs.flatMap((c) => Array.from({ length: 24 }, (_, i) => c(i / 23))), [segs]);
  useFrame((state) => {
    if (!segs.length || !ball.current) return;
    const T = 0.9 * segs.length + 1.2; // run the whole path, then rest a beat on the root
    const t = Math.min(1, ((state.clock.elapsedTime % T) / (T - 1.2))) * segs.length;
    const i = Math.min(segs.length - 1, Math.floor(t));
    const [x, y, z] = segs[i](Math.min(1, t - i));
    ball.current.position.set(x, y, z);
    trail.current?.position.set(x, y, z);
    const k = (state.clock.elapsedTime * 6) % 1;
    trail.current?.scale.setScalar(1 + k * 1.6);
    if (trail.current) (trail.current.material as THREE.MeshBasicMaterial).opacity = 0.45 * (1 - k);
  });
  if (!segs.length) return null;
  return (
    <>
      <Line points={pts} color={C.raspberry} lineWidth={4.5} transparent opacity={0.85} />
      {!reduced && (
        <>
          <mesh ref={ball}><sphereGeometry args={[0.17, 24, 16]} /><meshBasicMaterial color={C.saffron} toneMapped={false} /></mesh>
          <mesh ref={trail}><sphereGeometry args={[0.17, 24, 16]} /><meshBasicMaterial color={C.saffron} transparent depthWrite={false} /></mesh>
        </>
      )}
    </>
  );
}

function HealWave({ at, onDone }: { at: P3; onDone: () => void }) {
  const rings = useRef<THREE.Group>(null);
  const t0 = useRef(performance.now());
  useFrame(() => {
    const g = rings.current;
    if (!g) return;
    const t = (performance.now() - t0.current) / 2600;
    if (t >= 1) { onDone(); return; }
    g.children.forEach((m, i) => {
      const k = Math.max(0, t - i * 0.12);
      m.scale.setScalar(0.5 + easeOut(k) * 34);
      ((m as THREE.Mesh).material as THREE.MeshBasicMaterial).opacity = 0.5 * (1 - k);
    });
  });
  return (
    <group ref={rings} position={[at[0], 0.03, at[2]]}>
      {[0, 1, 2].map((i) => (
        <mesh key={i} rotation-x={-Math.PI / 2}>
          <ringGeometry args={[0.96, 1, 96]} />
          <meshBasicMaterial color={C.eucalyptus} transparent depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
}

// ---------------------------------------------------------------------------------------------- camera
function Director({ pos, focusIds, director, frame }: { pos: Record<string, P3>; focusIds: string[]; director: boolean; frame: number }) {
  const { camera } = useThree();
  const controls = useRef<{ target: THREE.Vector3; update: () => void; addEventListener: (e: string, f: () => void) => void } | null>(null);
  const userUntil = useRef(0);
  const angle = useRef(0.35);
  useEffect(() => {
    const c = controls.current;
    if (!c) return;
    c.addEventListener("start", () => { userUntil.current = performance.now() + 12000; });
  }, []);
  useFrame((_, dt) => {
    const c = controls.current;
    if (!c || !director || reduced || performance.now() < userUntil.current) return;
    // frame everything in focus (the evidence path and its root, or one picked node)
    const pts = focusIds.map((id) => pos[id]).filter(Boolean);
    const f = pts.length > 0;
    angle.current += dt * (f ? 0.07 : 0.05);
    const target = f
      ? new THREE.Vector3(...pts.reduce((s, p) => [s[0] + p[0] / pts.length, s[1] + p[1] / pts.length, s[2] + p[2] / pts.length], [0, 0, 0]))
      : new THREE.Vector3(0, 0.8, 0);
    const span = f ? Math.max(...pts.map((p) => Math.hypot(p[0] - target.x, p[2] - target.z))) : 0;
    const radius = f ? Math.min(26, Math.max(pts.length > 1 ? 13 : 9, span * 2.1 + 6)) : 25;
    const height = f ? radius * 0.55 : 12.5;
    const want = new THREE.Vector3(target.x + Math.sin(angle.current) * radius, height,
                                   target.z + Math.cos(angle.current) * radius);
    // shift the framing so the focus sits in the open space left of centre, clear of the dossier
    const right = new THREE.Vector3().subVectors(target, want).cross(camera.up).normalize().multiplyScalar((f ? 2.6 : 3.5) * frame);
    target.add(right);
    want.add(right);
    const k = 1 - Math.exp(-dt * (f ? 0.9 : 0.6));
    c.target.lerp(target, k);
    camera.position.lerp(want, k);
    c.update();
  });
  return <OrbitControls ref={controls as never} makeDefault enableDamping dampingFactor={0.08} maxPolarAngle={1.38}
                        minDistance={4} maxDistance={60} />;
}
