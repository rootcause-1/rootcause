// purpose: Which incident members each member BLAMES (to tell real dependencies from symptoms of a change)
// algorithm: -
MATCH (v:Anomalous)-[:BLAMES]->(d:Anomalous)
WHERE v.id IN $members
RETURN v.id AS id, collect(d.id) AS targets
