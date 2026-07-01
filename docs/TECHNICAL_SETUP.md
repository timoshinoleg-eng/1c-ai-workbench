# 1C AI Dev Workbench — Technical Setup

> **Язык / Language:** этот документ на английском. Описание настройки opencode на русском — в [`OPENCODE_SETUP_RU.md`](OPENCODE_SETUP_RU.md).

This is a technical setup guide for developers and integrators.

## 1. What this is

A local MVP stand for asking an MCP-capable AI client questions about a 1C configuration exported to files. The stand indexes a local copy of the dump and exposes it through `bsl-indexer` from `code-index-mcp`.

## 2. Requirements

- Windows 10/11.
- PowerShell 5.1+.
- Git for Windows.
- Rust toolchain with `cargo` and `rustc` in PATH.
- A 1C configuration dump in `C:\1c-ai-client\dump`.
- Cursor, VS Code with MCP support, Claude Desktop, or another MCP client.

## 3. Prepare the 1C dump

Put an exported 1C configuration into:

```powershell
C:\1c-ai-client\dump
```

Use a copy/export only. Do not point 1C AI Dev Workbench at a live 1C database. The scripts mirror this folder into `C:\1c-ai-workbench\generated\index\source-mirror` before indexing so the original dump is not modified.

## 4. Run scripts in order

Open PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd C:\1c-ai-workbench
.\scripts\01_check_env.ps1
.\scripts\02_clone_repos.ps1
.\scripts\03_build_bsl_indexer.ps1
.\scripts\04_index_1c_dump.ps1 -DumpRoot "C:\1c-ai-client\dump" -Force
.\scripts\06_healthcheck.ps1
```

If `04_index_1c_dump.ps1` says the dump is empty, copy the 1C files to `C:\1c-ai-client\dump` and rerun it.

## 5. Connect Cursor / VS Code

Templates are in `C:\1c-ai-workbench\configs`:

- `cursor-mcp.json` — template for Cursor-style `mcpServers`.
- `vscode-mcp.json` — template for VS Code MCP settings; verify exact schema in your VS Code extension/version.
- `claude-desktop-mcp.json` — template for Claude Desktop.

Default mode is `stdio`: the client starts `bsl-indexer.exe` directly. This avoids opening a local port.

For HTTP-capable clients, run:

```powershell
.\scripts\05_run_mcp_server.ps1 -Transport http -Port 8011
```

Then point the client at `http://127.0.0.1:8011/mcp` if the client supports streamable HTTP MCP.

## 6. Ask the first question

Use `demo-questions\questions_basic.md`. Start with:

```text
Какие объекты конфигурации найдены? Верни путь к файлу и способ ручной проверки.
```

## 7. How to know it works

A working answer contains:

- object/module names from the dump;
- a local file path under `generated\index\source-mirror`;
- a found module/procedure/function when available;
- a short code or metadata fragment;
- manual verification steps for Configurator or EDT.

`06_healthcheck.ps1` also writes:

- `logs\stats.json`;
- `logs\smoke-search-text.txt`;
- `logs\06_healthcheck.log`.

## 8. How to stop

- `stdio`: stop/disable the MCP client session.
- HTTP: press `Ctrl+C` in the PowerShell window that runs `05_run_mcp_server.ps1`.

## 9. Logs

Logs are in:

```powershell
C:\1c-ai-workbench\logs
```

Generated indexes and mirror data are in:

```powershell
C:\1c-ai-workbench\generated
```

## 10. opencode

opencode can be used instead of Cursor or VS Code. See:

- `configs\opencode-mcp.jsonc`
- `docs\OPENCODE_SETUP_RU.md`

Default MCP mode remains local `stdio`:

```powershell
C:\1c-ai-workbench\tools\code-index-mcp\target\release\bsl-indexer.exe serve --path onec=C:\1c-ai-workbench\generated\index\source-mirror --transport stdio
```

## 11. Pilot and sales materials

- Actual v0 launch pack: `docs\MVP_V0_LAUNCH_PACK_ACTUAL.md`
- Security overview: `docs\SECURITY_OVERVIEW.md`
- Golden demo answers: `demo-answers\golden_answers_summary.md`

## 12. Расширенное демо для первого знакомства

Открыть:

```powershell
cd C:\1c-ai-workbench
.\scripts\11_open_demo_showcase.ps1
```

Сценарий рассказа: `demo-showcase\TALK_TRACK.md`.

## 13. Инструкция для бизнес-партнёра

