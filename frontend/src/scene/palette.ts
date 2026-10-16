// One palette for the 3D scene and the DOM. Colour only ever means state:
// eucalyptus = healthy traffic, saffron = a symptom (alerting), raspberry = the root cause.
export const C = {
  porcelain: "#F2F3EE", // ground, fog, page
  paper: "#FBFBF7",     // panels
  pine: "#17312A",      // ink
  pineSoft: "#4C6158",  // secondary ink
  mist: "#DCE3DA",      // hairlines, idle nodes
  eucalyptus: "#5FA37F",
  eucalyptusLight: "#A9D3BA",
  saffron: "#F0A830",
  raspberry: "#D6265C",
  plum: "#7B4B94",      // predictions (what-if)
  lake: "#2F7FA8",      // blast radius (who depends on the root cause)
} as const;

/** Edge colour by error rate: healthy -> symptom -> failing. */
export function errColour(err?: number | null): string {
  const e = err ?? 0;
  if (e >= 0.05) return C.raspberry;
  if (e >= 0.01) return C.saffron;
  return C.eucalyptusLight;
}
