# Install Profiles

`START_HERE.ps1` now starts with a guided setup wizard by default. The old menu is still available with:

```powershell
.\START_HERE.ps1 -Menu
```

## Demo

For a short visual walkthrough.

Flow:

1. Open demo showcase.
2. Run readiness check.
3. Open First 10 Minutes.
4. Run a local search smoke test.

## Partner

For pilot setup and client handoff.

Flow:

1. Show the 1C dump folder.
2. Index the dump.
3. Run healthcheck and generate readiness dashboard.
4. Open First 10 Minutes and role-based packs.

## Developer

For 1C developers and tech leads.

Flow:

1. Ensure `bsl-indexer.exe` exists or build it.
2. Index the dump.
3. Run healthcheck.
4. Run Risk Scan and Explain Module.

## Advanced AI

For MCP client setup and AI agent workflows.

Flow:

1. Run healthcheck.
2. Open MCP Setup Assistant.
3. Show Prompt Gallery.
4. Show AI Rules.
5. Configure `live-1c-bridge` manually after 1C COM access is ready.

## Source of truth

Profile metadata lives in:

```text
configs\install-profiles.json
```

The wizard implementation lives in:

```text
START_HERE.ps1
```
