// purpose: Zero the live metrics of services, calls, queues and journeys with no spans in the window
// algorithm: -
MATCH (s:Service)
WHERE s.last_seen < $cutoff AND s.rps > 0
SET s.rps = 0.0, s.server_spans = 0, s.err_rate = 0.0, s.self_err_rate = 0.0, s.op_err_rate = 0.0
;
MATCH ()-[c:CALLS]->()
WHERE c.last_seen < $cutoff AND c.rps > 0
SET c.rps = 0.0, c.err_rate = 0.0, c.unanswered_rate = 0.0
;
MATCH ()-[c:CALLED_BY]->()
WHERE c.last_seen < $cutoff AND c.rps > 0
SET c.rps = 0.0, c.err_rate = 0.0
;
MATCH (j:Journey)
WHERE j.last_seen < $cutoff AND j.rps > 0
SET j.rps = 0.0
;
MATCH (qu:Queue)
WHERE qu.last_seen < $cutoff AND (qu.produce_rate > 0 OR qu.consume_rate > 0)
SET qu.produce_rate = 0.0, qu.consume_rate = 0.0
