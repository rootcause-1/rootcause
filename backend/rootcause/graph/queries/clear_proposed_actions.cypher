// purpose: Delete an incident's not-yet-approved proposals before proposing again
// algorithm: -
MATCH (a:Action)
WHERE a.incident_id = $id AND a.status = 'proposed'
DELETE a
