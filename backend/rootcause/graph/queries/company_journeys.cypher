// purpose: Company setup: customer journeys and the routes that identify them
// algorithm: -
MATCH (j:Journey)
RETURN j.id AS id, j.name AS name, j.routes AS routes
ORDER BY id
