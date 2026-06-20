# `.devin/` configuration

Configuration for the Devin CLI / Windsurf agent in this repo.

## Files

| File | Committed? | Purpose |
| --- | --- | --- |
| `config.json` | Yes (shared) | Team-shared config: MCP servers, permissions. **Never put API keys/secrets here.** |
| `config.local.json` | No (gitignored) | Personal overrides, including secrets. Overrides `config.json`. |
| `skills/` | Yes (shared) | Installed Agent Skills (see `skills/README.md`). |

## MCP servers & secrets

`config.json` is committed to git, so it must not contain secrets. Secret values
are referenced indirectly and resolved at runtime:

- `${env:VAR}` — read from an environment variable
- `${file:/path}` — read from a file

### Cala MCP server

`config.json` defines the `cala` server with its API key referenced as
`${env:CALA_API_KEY}`. To use it, provide the key locally (one of):

- Set the `CALA_API_KEY` environment variable (recommended), e.g. on Windows:
  `setx CALA_API_KEY "<your-cala-key>"` (restart the CLI afterwards), or
- Add a personal override in `config.local.json` (gitignored):
  ```json
  {
    "mcpServers": {
      "cala": {
        "url": "https://api.cala.ai/mcp/",
        "transport": "http",
        "headers": { "X-API-KEY": "<your-cala-key>" }
      }
    }
  }
  ```

Get a key from the Cala dashboard. Restart the CLI after changing config or env vars.
