// purpose: Record a container Change (restart / die) from docker events and link it to the Container
// algorithm: -
MERGE (k:Container {id: $container})
CREATE (c:Change {id: $id, kind: $kind, ts: $ts, actor: $actor, detail: $detail})
CREATE (c)-[:CHANGED]->(k)
RETURN c.id AS id
