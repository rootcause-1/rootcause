// purpose: Derive FeatureFlag-AFFECTS->Service from flag evaluations seen on spans (feature_flag.key events)
// algorithm: -
UNWIND $rows AS r
MERGE (f:FeatureFlag {id: r.flag})
MERGE (s:Service {id: r.svc})
MERGE (f)-[a:AFFECTS]->(s)
SET a.source = 'spans', a.last_seen = $now
