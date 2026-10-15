// purpose: List firing alerts (detector hysteresis, incident membership, self-signal z-scores)
// algorithm: -
MATCH (a:Alert)
WHERE a.status = 'firing'
RETURN a.id AS id, a.kind AS kind, a.target AS target, a.ts AS ts, a.value AS value, a.baseline AS baseline,
       a.dev AS dev, a.threshold AS threshold
