// purpose: List incidents by status ('open', 'resolved' or 'all'), newest first
// algorithm: -
MATCH (i:Incident)
WHERE i.status <> 'snapshot' AND ($status = 'all' OR i.status = $status)
RETURN properties(i) AS incident
ORDER BY i.created_ts DESC
LIMIT 50
