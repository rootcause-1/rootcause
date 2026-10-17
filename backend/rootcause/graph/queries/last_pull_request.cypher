// purpose: Fix it in code: when RootCause last opened a pull request (cooldown for the public site)
// algorithm: -
MATCH (p:PullRequest)
RETURN p.ts AS ts, p.id AS url
ORDER BY p.ts DESC
LIMIT 1
