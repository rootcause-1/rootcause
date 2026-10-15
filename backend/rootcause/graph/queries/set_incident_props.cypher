// purpose: Merge properties onto an incident (agent verdict JSON, state, confidence)
// algorithm: -
MATCH (i:Incident {id: $id})
SET i += $props
