// purpose: Codebase drift: calls seen in traffic that the code never declares, and declared dependencies never used
// algorithm: -
MATCH (ma:CodeModule)-[:IMPLEMENTS]->(a:Service)-[:CALLS]->(b:Service)<-[:IMPLEMENTS]-(mb:CodeModule)
WHERE NOT (ma)-[:DECLARES]->(mb)
RETURN 'undeclared' AS kind, a.id AS src, b.id AS dst
UNION
MATCH (ma:CodeModule)-[:DECLARES]->(mb:CodeModule)
MATCH (ma)-[:IMPLEMENTS]->(a:Service)
MATCH (mb)-[:IMPLEMENTS]->(b)
WHERE (a)-[:CALLS]->() AND ((b)<-[:CALLS]-() OR (b)<-[:USES]-())
  AND NOT (a)-[:CALLS]->(b) AND NOT (a)-[:USES]->(b)
RETURN 'unused' AS kind, a.id AS src, b.id AS dst
