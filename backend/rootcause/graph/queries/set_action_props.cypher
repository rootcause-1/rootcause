// purpose: Merge properties onto an Action (approval token hash, status, result)
// algorithm: -
MATCH (a:Action {id: $id})
SET a += $props
