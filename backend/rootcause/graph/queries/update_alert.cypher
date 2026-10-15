// purpose: Refresh the latest value of a firing alert
// algorithm: -
MATCH (a:Alert {id: $id})
SET a.value = $value, a.last_ts = $ts
