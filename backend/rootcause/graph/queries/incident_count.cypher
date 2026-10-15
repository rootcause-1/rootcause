// purpose: Count incidents (next INC-xxxx number)
// algorithm: -
MATCH (i:Incident)
WHERE i.status <> 'snapshot'
RETURN count(i) AS n
