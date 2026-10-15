// purpose: Merge a map of properties onto nodes by id (agent metrics, Prometheus samples, baselines, rule counters)
// algorithm: -
UNWIND $rows AS r
MATCH (n {id: r.id})
SET n += r.props
