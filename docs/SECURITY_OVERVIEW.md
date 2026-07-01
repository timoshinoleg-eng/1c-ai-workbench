# 1C AI Workbench — Security Overview

The workbench is **read-only by default**, runs locally, and binds to `127.0.0.1` only.

Key properties:

- All MCP servers use stdio transport. Optional HTTP binds to loopback.
- The index is a local SQLite DB under `generated/`.
- `live-1c-bridge` and `ibcmd-bridge` are disabled by default.
- The workbench does not phone home, bundle 1C binaries, or ship telemetry.
- Prompt injection via dump content is a client-side responsibility.

Full threat model, controls, and pilot audit checklist are available
under a commercial agreement.
