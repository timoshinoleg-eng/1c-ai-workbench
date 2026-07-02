# Security Notes

> **Язык / Language:** этот документ на английском. Подробный русскоязычный Security Playbook для пилота — в [`SECURITY_PILOT_PLAYBOOK.md`](SECURITY_PILOT_PLAYBOOK.md).

## What stays local

- The 1C dump in `C:\1c-ai-client\dump`.
- The mirrored copy in `C:\1c-ai-workbench\generated\index\source-mirror`.
- The SQLite index under `.code-index\index.db`.
- Build artifacts in `tools\code-index-mcp\target`.
- Logs in `C:\1c-ai-workbench\logs`.

## What is not sent to the implementer

The scripts do not upload the 1C dump to any external API or cloud service. They clone open-source repositories and build a local binary. Indexing runs locally.

## When data can leave the machine

If Cursor, VS Code, desktop MCP client, or another MCP client sends retrieved snippets to an external service provider, those snippets may leave the machine according to that client's provider/account settings. This is controlled by the client, not by the 1C AI Dev Workbench scripts.

## API keys

Use only client-owned API keys. Do not store real keys in this repository, README files, screenshots, or issue reports. `configs\external-client.env.example` is a placeholder only.

## Production database rule

Do not test on a live production 1C database. Use an export/copy. This MVP does not write to 1C, but operational mistakes around live bases are unnecessary risk.

## Third-party skill boundary

`tools\cc-1c-skills` is vendored as an upstream reference via git subtree
(see `tools/SUBTREE.md` for the pinned SHA and sync workflow; **not** a
git submodule — the canonical copy lives in the superproject's working
tree). The production package and installer only include the read-only
skill folders used by `skills-bridge` (`cf-info`, `cfe-diff`,
`form-validate`, `meta-validate`, `mxl-info`, `subsystem-info`).
Write-oriented upstream folders such as `subsystem-compile` are not part
of the production runtime surface; the installer exclude list and the
skills-bridge tool list both filter them out.

## AI answer rule

AI answers are search/navigation output. They are not automatic 1C changes and they are not approval to change business logic. A 1C developer verifies every answer manually.
