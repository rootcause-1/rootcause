// purpose: Journeys that REQUIRE any failing node, with current vs baseline success rate
// algorithm: -
MATCH (j:Journey)-[r:REQUIRES]->(s)
WHERE s.id IN $failing
RETURN j.id AS journey, j.success_rate AS now, j.bl_success_rate AS baseline, collect(s.id) AS via
