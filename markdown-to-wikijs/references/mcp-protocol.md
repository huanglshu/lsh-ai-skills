# Wiki.js MCP transport notes

Read this reference only when a configured MCP server fails to connect or when
the Wiki.js MCP does not expose the expected tool names.

## Supported client configuration

The publisher reads `[mcp_servers.<name>]` directly from Codex `config.toml`.
Supported transports:

- stdio: `command`, `args`, optional `env` and `cwd`;
- streamable HTTP: `url`, optional `http_headers`, `env_http_headers`, and
  `bearer_token_env_var`.

The name is resolved on every publish. This is deliberately separate from the
model's already-loaded tool inventory.

## Expected tools

The default `@ni-c/wikijs-mcp` server exposes the required tools:

- `get_page`
- `create_page`
- `update_page`
- `list_asset_folders`
- `create_asset_folder`
- `upload_asset`
- `list_assets`

The publisher does not use destructive, administrative, page-delete, or
asset-delete tools.

## Common failures

- `MCP server "<name>" is not configured`: fix `mcp_server_name` in
  `config.json` or rename the `[mcp_servers.<name>]` table.
- `Could not launch MCP server`: verify the command and environment. For the
  Node.js server, Node must be 22 or newer.
- HTTP and HTTPS are supported. An explicitly supplied `--scheme` changes the
  scheme for this invocation only; it does not switch host or port or modify
  `config.toml`. HTTPS certificate verification remains enabled.
- A tool-not-found response: the configured server is not a Wiki.js MCP or its
  allowlist filtered a required write tool.
- A path-scope error: adjust the Wiki.js server's `WIKIJS_ALLOWED_PATHS` or
  choose an authorized page path and English document name.
- An elicitation request: the headless publisher refuses to answer person-only
  approval prompts. Use non-destructive tools or grant the required scope.

The publisher constructs root-relative URLs from the actual folder slugs and
filenames returned by Wiki.js. For stdio servers, it verifies rendered HTML
through `get_page` and, when `WIKIJS_URL` and `WIKIJS_TOKEN` or
`WIKIJS_API_KEY` are configured, downloads each resource with the same
credentials and compares its digest (missing endpoint or credentials on stdio
leaves the download check incomplete). For `streamable-http` MCP servers,
remote resource display verification is skipped. The publisher rejects
redirects during credentialed checks.
