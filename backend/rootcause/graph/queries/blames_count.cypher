// purpose: Number of BLAMES edges (guards algo.WCC, which ignores filters on missing relationship types)
// algorithm: -
MATCH ()-[b:BLAMES]->()
RETURN count(b) AS n
