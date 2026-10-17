// purpose: Company setup: every service the graph has seen (to assign owners and runbooks)
// algorithm: -
MATCH (s:Service)
RETURN s.id AS id
ORDER BY id
