---
name: markdown-to-wikijs
description: Convert a document to Markdown and publish it and its images or PDF attachments to Wiki.js through a named MCP server. Use when the user asks to convert a file and upload or publish it to Wiki.js, or publish existing Markdown with attachments.
---

# Markdown to Wiki.js

Convert locally using the `markdown-converter` skill, then publish through the
configured Wiki.js MCP only when the user requests publication.

## Configuration

`config.json` contains only the MCP name:

```json
{"mcp_server_name": "wiki-local"}
```

Read it each time the skill is used. The publisher also re-reads it on every
`plan`, `apply`, and `check`, and starts a fresh MCP connection. A changed name
therefore takes effect on the next command in the current session. It resolves
the name from `config.toml` in `CODEX_HOME`, or `~/.codex/config.toml` when
`CODEX_HOME` is unset. The chosen server must expose the Wiki.js tools listed
in [references/mcp-protocol.md](references/mcp-protocol.md). Changing the name
does not itself configure an MCP server.

## Conversion and destination

Read and follow the `markdown-converter` skill. Verify local attachments before
publishing. Ask for the complete Wiki.js page path if the user has not given
it, for example `manuals/user-guide`. Do not infer a destination or interpret
the supplied path as merely a parent directory.

Choose a meaningful English name for the document from its title or filename,
translating Chinese names as needed. Use lowercase English letters, digits and
hyphens, for example `user-guide`. The publisher stores attachments in
`assets/<english-document-name>/` independently of the page path. Existing
Markdown is also accepted.

After converting, run `python scripts/publish_wikijs.py normalize --markdown
"<markdown-file>"` to merge adjacent bold spans produced by conversion. The
command preserves literal stars in code and updates the local file in place.
Planning also normalizes these spans in the published copy without changing the
local file. Inspect conversion output when other malformed formatting remains.

Images are named `image_0001.png`, `image_0002.jpg`, etc. PDFs are named
`pdf_0001.pdf`, `pdf_0002.pdf`, etc. Each category has its own counter,
starting at 0001, in first-reference order. Duplicate references to the same
local file share one upload and URL. Other attachment types, including active
SVG/HTML, are rejected. Links in the published Markdown use these names.

The MCP server chooses the default Wiki.js locale; use `--locale` when the user
specifies another locale. The document title defaults to the Markdown frontmatter title
or its filename and can be overridden with `--title`.

## Plan and publish

Run these commands from this skill directory (on Windows, use the selected
Python 3.11+ interpreter). Do not write the plan over an existing unrelated
file. The plan contains the document text and local file paths; treat it as
potentially sensitive.

```powershell
python scripts/publish_wikijs.py plan `
  --markdown "C:\work\user-guide.md" `
  --document-path "manuals/user-guide" `
  --document-name "user-guide" `
  --output "C:\work\wikijs-plan.json"

python scripts/publish_wikijs.py apply --plan "C:\work\wikijs-plan.json"
```

If the filename is already English, `--document-name` may be omitted. For
non-English filenames provide the translated English name explicitly. The plan
is local only. `apply --dry-run` performs remote reads only. `check` performs a
fresh MCP handshake and checks the expected tools without writing to Wiki.js.
The script reconnects using the current configured MCP name even when the name
was changed after planning; the supplied page path and English name remain
unchanged. A changed source file or attachment invalidates the plan.

Both HTTP and HTTPS are supported. To select the protocol for one invocation,
pass `--scheme http` or `--scheme https` to `apply`, `verify`, or `check`.
For a stdio MCP this changes only the scheme of `WIKIJS_URL` in the launched
process; for a streamable-HTTP MCP it changes only its endpoint scheme. The
host, port and persistent configuration are unchanged. Without `--scheme`,
the configured URL is used exactly as-is. Never silently downgrade HTTPS:
HTTP can expose credentials and document contents, especially off localhost.

After publishing, the script reads the rendered page and confirms each
referenced image or attachment appears as the intended image or link. It then
downloads each resource from the configured Wiki.js origin with the MCP's
Wiki.js credentials and compares its bytes to the local file. It does not
follow redirects, change protocols, or send credentials to other origins.
This verifies the server-rendered HTML and file contents, not the display in
every reader's browser or that reader's permissions. If the connection or
credentials needed to download files are unavailable, report verification as
incomplete, not as success. A failed check may occur after the page was written.

To recheck an already-published page without changing it:

```powershell
python scripts/publish_wikijs.py verify `
  --markdown "C:\work\user-guide.md" `
  --document-path "manuals/user-guide" `
  --document-name "user-guide"
```

If the target page already exists, ask the user before replacing its entire
content. Then use `apply --replace`; concurrent page edits remain protected.
If a remote attachment already has a planned name, stop and report the
conflict: name equality alone does not establish content equality. Do not
overwrite, delete, or reuse it without verified content. Choose another English
document name with the user's agreement and create a new plan if appropriate.

## Report

Report the MCP name, page path and locale, attachment folder and uploaded
count, whether the page was created or replaced, and the verification result.
If a write fails partway through, report that uploaded attachments or folders
may remain; do not delete them automatically.
