// purpose: Create a proposed remediation Action for an incident (with risk + side effects)
// algorithm: -
CREATE (a:Action {id: $id, incident_id: $incident, kind: $kind, target: $target, params: $params, risk: $risk,
                  side_effects: $side_effects, reason: $reason, rank: $rank, status: 'proposed', ts: $now})
RETURN a.id AS id
