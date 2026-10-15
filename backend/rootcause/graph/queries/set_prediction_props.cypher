// purpose: Store precision/recall on a Prediction after the break
// algorithm: -
MATCH (p:Prediction {id: $id})
SET p += $props
