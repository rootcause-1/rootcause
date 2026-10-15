// purpose: Create a new open Incident for a new BLAMES component
// algorithm: -
CREATE (i:Incident {id: $id, status: 'open', created_ts: $now, onset_ts: $onset, members: $members,
                    quiet_ticks: 0, agent_state: 'pending'})
RETURN i.id AS id
