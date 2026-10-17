// One palette for the service map (SVG) and the DOM (warm paper theme). Colour only ever means state:
// eucalyptus = healthy, saffron = a symptom (alerting), raspberry = the root cause / failing requests.
export const C = {
  porcelain: "#F5F3EA", // page (warm cream)
  paper: "#FBFAF5",     // panels
  card: "#FFFFFF",
  pine: "#1E2621",      // ink
  pineSoft: "#6E726A",  // secondary ink
  mist: "#E2DED0",      // hairlines
  line: "#CFCBBB",      // healthy edges
  eucalyptus: "#1F5C45", // healthy / brand green
  eucalyptusLight: "#CFCBBB",
  saffron: "#D98E2F",
  raspberry: "#D2513F",
  plum: "#7C66C7",      // predictions (what-if)
  lake: "#9C86E8",      // touched by the fix (lilac)
  // isometric box faces: [top, left, right]
  boxIdle: ["#F1EFE7", "#DEDBD0", "#E9E6DC"],
  boxHot: ["#F6D9B4", "#E3B67F", "#EEC795"],
  boxRoot: ["#EFA597", "#C9604E", "#DD7B69"],
  boxUser: ["#E4DCFA", "#B7A8E6", "#CDC1F2"],
  boxStore: ["#E6E9EE", "#C8CDD6", "#D8DCE3"],
} as const;

/** Edge colour by error rate: healthy -> symptom -> failing. */
export function errColour(err?: number | null): string {
  const e = err ?? 0;
  if (e >= 0.05) return C.raspberry;
  if (e >= 0.01) return C.saffron;
  return C.eucalyptusLight;
}
