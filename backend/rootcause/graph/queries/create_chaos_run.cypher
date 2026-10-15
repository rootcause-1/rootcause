// purpose: Record one blind chaos run and its scores in the rc_eval_<batch> graph
// algorithm: -
CREATE (r:ChaosRun {id: $id, batch: $batch, flag: $flag, variant: $variant, truth: $truth, class: $class, ts: $now,
                    seed: $seed, verdict: $verdict, top1: $top1, top3: $top3, ttd_ms: $ttd_ms, incident_id: $incident_id,
                    results: $results, miss_reason: $miss_reason})
RETURN r.id AS id
