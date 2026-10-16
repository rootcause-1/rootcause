// purpose: UI snapshot: customer journeys with live traffic and success vs baseline, and the services each one critically needs
// algorithm: -
MATCH (j:Journey)
OPTIONAL MATCH (j)-[r:REQUIRES]->(s:Service)
WHERE r.critical = true
RETURN j.id AS id, j.name AS name, j.rps AS rps, j.success_rate AS success_rate, j.bl_success_rate AS baseline,
       collect(s.id) AS needs
