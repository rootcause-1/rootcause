// purpose: Record SIMILAR_TO {score} edges from an incident to strongly matching past incidents
// algorithm: -
MATCH (i:Incident {id: $id})
UNWIND $similar AS sim
MATCH (p:Incident {id: sim.incident})
MERGE (i)-[r:SIMILAR_TO]->(p)
SET r.score = sim.score
