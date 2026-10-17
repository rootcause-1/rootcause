// purpose: Codebase: one CodeModule per service folder (language, files, lines, CODEOWNERS), CONTAINED in the repo
// algorithm: -
UNWIND $modules AS m
MERGE (c:CodeModule {id: 'code:' + m.name})
SET c.name = m.name, c.path = m.path, c.language = m.language, c.files = m.files, c.loc = m.loc,
    c.owners = m.owners, c.kind = m.kind
WITH c
MATCH (r:Repo {id: $id})
MERGE (r)-[:CONTAINS]->(c)
