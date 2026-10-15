// purpose: Datastores a service USES and journeys that REQUIRE it (restart side effects, statefulness)
// algorithm: -
MATCH (s:Service {id: $id})
OPTIONAL MATCH (s)-[:USES]->(d:Datastore)
WITH s, collect(DISTINCT d.id) AS datastores
OPTIONAL MATCH (j:Journey)-[:REQUIRES]->(s)
RETURN datastores, collect(DISTINCT j.id) AS journeys
