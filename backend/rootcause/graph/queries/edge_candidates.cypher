// purpose: Connection causes: a caller's calls go unanswered/fail while the callee's server traffic vanished (<= 10% of its baseline)
// algorithm: -
MATCH (a:Service)-[c:CALLS]->(b:Service)
WHERE a.id IN $members
  AND (coalesce(c.unanswered_rate, 0.0) > 0 OR coalesce(c.err_rate, 0.0) > 0.5)
  AND coalesce(b.bl_rps, 0.0) > 0 AND coalesce(b.rps, 0.0) <= 0.1 * b.bl_rps
RETURN a.id AS caller, b.id AS callee, c.unanswered_rate AS unanswered_rate, c.err_rate AS err_rate
