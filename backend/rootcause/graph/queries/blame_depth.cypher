// purpose: Out/in degree of each incident member in BLAMES (out_degree 0 = deepest, nothing further to blame)
// algorithm: -
MATCH (v:Anomalous)
WHERE v.id IN $members
OPTIONAL MATCH (v)-[:BLAMES]->(d:Anomalous)
WITH v, count(d) AS out_degree
OPTIONAL MATCH (u:Anomalous)-[:BLAMES]->(v)
RETURN v.id AS id, out_degree, count(u) AS in_degree, labels(v) AS labels,
       v.self_err_rate AS self_err_rate, v.rps AS rps
