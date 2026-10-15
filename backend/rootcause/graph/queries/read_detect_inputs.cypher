// purpose: Read every alertable node (Service, Queue, Datastore) and Journey with its live metrics and stored baselines
// algorithm: -
MATCH (n)
WHERE n:Service OR n:Queue OR n:Datastore OR n:Journey
RETURN n.id AS id, labels(n) AS labels, properties(n) AS props
