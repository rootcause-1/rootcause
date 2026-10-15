// purpose: All actions of an incident in proposal order
// algorithm: -
MATCH (a:Action)
WHERE a.incident_id = $id
RETURN properties(a) AS action
ORDER BY a.ts, a.rank
