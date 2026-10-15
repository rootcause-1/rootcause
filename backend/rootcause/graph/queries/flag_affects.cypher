// purpose: Services a feature flag AFFECTS and its current variant (safety report for a flag revert)
// algorithm: -
MATCH (f:FeatureFlag {id: $flag})
OPTIONAL MATCH (f)-[:AFFECTS]->(s)
RETURN f.id AS flag, f.variant AS variant, collect(s.id) AS services
