// purpose: Codebase: feature flag keys the graph knows (to look for where the code reads them)
// algorithm: -
MATCH (f:FeatureFlag)
RETURN f.id AS id
