// purpose: Seed user journeys and the routes that identify their root spans
// algorithm: -
UNWIND $journeys AS j
MERGE (n:Journey {id: j.id})
SET n.name = j.name, n.routes = j.routes
