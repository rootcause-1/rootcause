// purpose: All chaos runs of an eval graph, oldest first (scorecard)
// algorithm: -
MATCH (r:ChaosRun)
RETURN properties(r) AS run
ORDER BY r.ts
