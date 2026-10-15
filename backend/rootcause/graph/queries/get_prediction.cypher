// purpose: Read a saved Prediction
// algorithm: -
MATCH (p:Prediction {id: $id})
RETURN properties(p) AS prediction
