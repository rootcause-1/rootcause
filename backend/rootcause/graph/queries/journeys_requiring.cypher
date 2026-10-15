// purpose: Journeys with a critical REQUIRES edge to any of the given services (prediction: broken journeys)
// algorithm: -
MATCH (j:Journey)-[r:REQUIRES]->(s)
WHERE s.id IN $services AND r.critical = true
RETURN DISTINCT j.id AS journey
