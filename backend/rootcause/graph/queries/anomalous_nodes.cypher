// purpose: Ids of all currently :Anomalous nodes (prediction precision/recall)
// algorithm: -
MATCH (n:Anomalous)
RETURN n.id AS id, labels(n) AS labels
