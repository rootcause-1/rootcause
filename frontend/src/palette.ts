// One palette for the service map (SVG) and the DOM (dark theme). Colour only ever means state:
// eucalyptus = healthy, saffron = a symptom (alerting), raspberry = the root cause / failing requests.
export const C = {
  porcelain: "#0A0F1C", // page
  paper: "#121A2B",     // panels, cards
  card: "#17213A",      // service cards on the map
  pine: "#E6EBF2",      // ink
  pineSoft: "#94A3B8",  // secondary ink
  mist: "#26324A",      // hairlines
  eucalyptus: "#10B981",
  eucalyptusLight: "#1F5F52", // healthy edges (quiet on a dark background)
  saffron: "#F59E0B",
  raspberry: "#F43F5E",
  plum: "#A78BFA",      // predictions (what-if)
  lake: "#38BDF8",      // touched by the fix
} as const;

/** Edge colour by error rate: healthy -> symptom -> failing. */
export function errColour(err?: number | null): string {
  const e = err ?? 0;
  if (e >= 0.05) return C.raspberry;
  if (e >= 0.01) return C.saffron;
  return C.eucalyptusLight;
}
