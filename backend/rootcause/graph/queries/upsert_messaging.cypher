// purpose: Write PRODUCES_TO / CONSUMED_BY edges and per-queue produce/consume rates from messaging spans
// algorithm: -
UNWIND $produces AS r
MERGE (s:Service {id: r.svc})
MERGE (qu:Queue {id: r.queue})
MERGE (s)-[p:PRODUCES_TO]->(qu)
SET p.rate = r.rate, p.last_seen = $now
;
UNWIND $consumes AS r
MERGE (qu:Queue {id: r.queue})
MERGE (s:Service {id: r.svc})
MERGE (qu)-[c:CONSUMED_BY]->(s)
SET c.rate = r.rate, c.group = r.group, c.last_seen = $now
;
UNWIND $queues AS r
MERGE (qu:Queue {id: r.queue})
SET qu.produce_rate = r.produce_rate, qu.consume_rate = r.consume_rate, qu.last_seen = $now
