// purpose: Seed the fallback FeatureFlag-AFFECTS->Service map (used when flag evaluations are not on spans)
// algorithm: -
UNWIND $flags AS f
MERGE (ff:FeatureFlag {id: f.id})
WITH ff, f
UNWIND f.services AS sid
MERGE (s:Service {id: sid})
MERGE (ff)-[:AFFECTS]->(s)
