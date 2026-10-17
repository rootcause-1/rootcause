// purpose: Codebase: the scanned repository and the commit it was scanned at
// algorithm: -
MERGE (r:Repo {id: $id})
SET r.url = $url, r.sha = $sha, r.scanned_ts = $now
