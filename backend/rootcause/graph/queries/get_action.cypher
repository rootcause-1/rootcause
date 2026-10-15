// purpose: Read one Action
// algorithm: -
MATCH (a:Action {id: $id})
RETURN properties(a) AS action
