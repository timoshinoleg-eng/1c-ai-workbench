# IPC contract

Every Tauri command exposed by the Rust core has a matching TypeScript
wrapper in `src/lib/api.ts`. The Rust types are the source of truth;
the TS types are derived by hand and must be kept in sync.

## Commands

### `list_servers`

```ts
invoke<McpServerInfo[]>("list_servers")
```

Returns the current snapshot of all 5 MCP server definitions, with
status derived from the running child map.

| Param | Type | Description |
| ----- | ---- | ----------- |
| —     | —    | —           |

Returns: `McpServerInfo[]` — see `src/types/mcp.ts`.

### `start_server`

```ts
invoke<void>("start_server", { name: "1c-code-index" })
```

Spawns the child process. Idempotent: returns `Ok(())` if the server
is already running.

Errors: `"server 'foo' is disabled"`, `"spawn failed: <os error>"`.

### `stop_server`

```ts
invoke<void>("stop_server", { name: "1c-code-index" })
```

Sends SIGKILL (`TerminateProcess` on Windows) to the child. Idempotent.

### `restart_server`

```ts
invoke<void>("restart_server", { name: "1c-code-index" })
```

`stop_server` followed by `start_server`. Returns the new state.

### `call_tool`

```ts
invoke<McpToolResult>("call_tool", {
  server: "1c-code-index",
  tool: "search_text",
  args: { query: "Номенклатура", limit: 20 },
})
```

Sends a JSON-RPC `tools/call` request over the child's stdin and reads
the first response line from stdout (15s timeout).

| Param   | Type                       | Description                      |
| ------- | -------------------------- | -------------------------------- |
| server  | `string`                   | MCP server id                    |
| tool    | `string`                   | Tool name registered by the server |
| args    | `Record<string, unknown>`   | Tool-specific arguments          |

Returns: `McpToolResult { ok, tool, server, elapsedMs, data, error }`.

### `get_status`

```ts
invoke<WorkbenchStatus>("get_status")
```

Returns:

- `dumpPath` — current dump dir from config.
- `indexExists` — `.code-index` directory presence.
- `indexFileCount` — recursive file count.
- `lastIndexedAt` — currently `null`; wired in v0.2.0.
- `serversRunning` / `serversTotal` — from the McpManager.
- `workbenchVersion` — from the parent `Cargo.toml`.

### `load_config`

```ts
invoke<CockpitConfig>("load_config")
```

Reads `%APPDATA%\1c-ai-cockpit\config.json` (or the default if
missing). Cached in `AppState`.

### `save_config`

```ts
invoke<void>("save_config", { config: CockpitConfig })
```

Persists the config and pushes per-server enable/disable changes into
`McpManager` (in-memory refresh, no child restart).

### `pick_dump_dir`

```ts
invoke<string | null>("pick_dump_dir")
```

Opens a native folder picker. Returns the selected absolute path or
`null` if the user cancelled.

### `run_healthcheck`

```ts
invoke<HealthReport>("run_healthcheck")
```

Runs the v0.1.0 health checks (workbench root, dump dir, bsl-indexer
binary, python on PATH). Each check returns a
`HealthCheckItem { name, area, status, message, whyItMatters, nextStep }`.
The aggregate status is `"Ready"` only if all checks pass.

### `ping_server`

```ts
invoke<{ ok: boolean; latencyMs: number }>("ping_server", { name })
```

Sends `{ "method": "ping" }` to the running child and measures the
round-trip. Errors if the child is not running or the request times
out.

### `open_config_file`

```ts
invoke<void>("open_config_file")
```

Opens `%APPDATA%\1c-ai-cockpit\config.json` in the default Windows
handler (typically Notepad). Windows-only; returns an error on
macOS / Linux.

## Adding a new command

1. Implement the function in `src-tauri/src/commands.rs`:

   ```rust
   #[tauri::command]
   pub fn my_command(state: State<'_, AppState>, arg: String) -> Result<String, String> {
       Ok(format!("got {arg}"))
   }
   ```

2. Register it in `src-tauri/src/lib.rs` inside
   `.invoke_handler(tauri::generate_handler![…])`.

3. Add a typed wrapper in `src/lib/api.ts`:

   ```ts
   export async function myCommand(arg: string): Promise<string> {
     return invoke<string>("my_command", { arg });
   }
   ```

4. If the command returns a new shape, add the type to
   `src/types/mcp.ts` (or a new file under `src/types/`) and to the
   matching Rust struct in `commands.rs`.

## Type safety

- Rust types use `#[derive(Serialize, Deserialize)]`; the JSON
  field names are the same as the TS field names (`camelCase` on
  the wire, `snake_case` in Rust via `#[serde(rename_all = "camelCase")]`
  is **not** used in v0.1.0 — fields are `snake_case` on both sides).
  This keeps the contract grep-friendly; switch to camelCase in
  v0.2.0 once we add a code generator (e.g. `ts-rs`).
- Runtime validation: Tauri 2.x rejects commands whose argument
  types do not match the expected JSON schema. We do not add a
  secondary validator (zod / valibot) in v0.1.0; the Rust enum +
  `Result<_, String>` is the error contract.
