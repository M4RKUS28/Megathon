# Devin API Sources

Official Devin API docs used for this implementation:

- API Overview: `https://docs.devin.ai/api-reference/overview`
- Authentication: `https://docs.devin.ai/api-reference/authentication`
- Get Self: `https://docs.devin.ai/api-reference/v3/self/self`
- Create Session: `https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions`
- Get Session: `https://docs.devin.ai/api-reference/v3/sessions/get-organizations-session`
- List Session Messages: `https://docs.devin.ai/api-reference/v3/sessions/get-organizations-session-messages`
- Send Session Message: `https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions-messages`
- List Organization Repositories: `https://docs.devin.ai/api-reference/v3/repositories/list-organizations-repositories`
- Get Repository Indexing Status: `https://docs.devin.ai/api-reference/v3/repositories/get-organizations-repository-indexing-status`
- Index Repository: `https://docs.devin.ai/api-reference/v3/repositories/put-organizations-index-repository`

The implementation uses API v3 for auth/session operations and v3beta1 for repository visibility/indexing preparation.
