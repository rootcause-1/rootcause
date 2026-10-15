// purpose: List open incidents with their member node ids (keeps incident ids stable across ticks)
// algorithm: -
MATCH (i:Incident)
WHERE i.status = 'open'
RETURN i.id AS id, i.members AS members, i.created_ts AS created_ts, i.onset_ts AS onset_ts,
       i.agent_state AS agent_state, i.quiet_ticks AS quiet_ticks
