# Production Onboarding Specification

> Version: 1.0-draft
> Status: Design — not implemented
> Base commit: `538db97` (Draft PR #3 head)
> Scope: user-facing production journey from clean Windows to first evidence-based AI answer

This specification defines the complete production onboarding path for 1C AI
Workbench. It is a design contract for subsequent implementation; it does not
change existing provider generators, Continue profiles, workflows, release
signing, or user settings.

---

## 1. Guiding principles

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | Read-only by default | No write to live 1C database at any onboarding stage |
| P2 | Local-first | Index, MCP servers, and logs stay on the operator's machine |
| P3 | Client-owned keys only | Generators never accept key values; Continue resolves the operator-owned local secret and sends authentication only to the selected provider |
| P4 | Fail-closed | Any unresolved prerequisite blocks progress with a clear message |
| P5 | No Workbench phone-home | Workbench-owned processes have zero telemetry, auto-update, or background network calls; VS Code, Continue, and provider traffic are audited separately |
| P6 | Evidence-first AI | Every AI answer must cite file, line/identifier, and confidence |
| P7 | Explicit human gate | BSL file changes require diff review and operator confirmation |
| P8 | Reversible | Every onboarding step can be undone without data loss |

---

## 2. User journey overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 1: INSTALL        Phase 2: CONFIGURE       Phase 3: USE     │
│                                                                     │
│  ┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌────────────┐  │
│  │ Clean    │──▶│ VS Code +    │──▶│ AI mode   │──▶│ Index 1C   │  │
│  │ Windows  │   │ Continue     │   │ selection │   │ dump/repo  │  │
│  └──────────┘   └──────────────┘   └───────────┘   └────────────┘  │
│       │               │                  │                │         │
│       ▼               ▼                  ▼                ▼         │
│  ┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌────────────┐  │
│  │ Workbench│   │ Key storage  │   │ MCP verify│──▶│ First AI   │  │
│  │ installer│   │ (BYOK)       │   │ Code+Help │   │ answer     │  │
│  └──────────┘   └──────────────┘   └───────────┘   └────────────┘  │
│                                                        │            │
│                                                        ▼            │
│                                                  ┌────────────┐    │
│                                                  │ BSL change  │    │
│                                                  │ proposal    │    │
│                                                  └────────────┘    │
│                                                        │            │
│                                                        ▼            │
│                                                  ┌────────────┐    │
│                                                  │ Diff review │    │
│                                                  │ + confirm   │    │
│                                                  └────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1 — Installation on clean Windows

### 3.1 Prerequisites (operator verifies before running installer)

| Requirement | Minimum | Check method |
|-------------|---------|--------------|
| OS | Windows 11 25H2 x64; Windows 10 22H2 x64 only with active ESU for legacy acceptance | `winver` + update/ESU status |
| RAM | 8 GB (16 GB recommended for local model) | System Properties |
| Disk | 2 GB free for workbench + index | Explorer |
| CPython | 3.11.x 64-bit | `python --version` |
| PowerShell | 5.1+ (ships with Windows) | `$PSVersionTable` |
| Network | Required only for online AI mode; offline mode needs none | — |

### 3.2 Installer behavior

The production installer is a per-user Inno Setup package (see
`docs/WINDOWS_EXE_INSTALLER.md`). Onboarding assumes:

1. Operator downloads the signed `.exe` and verifies SHA-256 against the
   published checksum.
2. Double-click launches the installer. No UAC elevation prompt appears
   (per-user install to `%LOCALAPPDATA%\1c-ai-workbench`).
3. Installer places: workbench scripts, `bsl-indexer.exe`, Python lock file,
   optional offline wheelhouse, documentation, and `START_HERE.ps1`.
4. Installer creates a Start Menu shortcut and an optional desktop shortcut.
5. Installer does NOT: install VS Code, install Continue, install Ollama,
   install Java, create Python venv, download any model, or contact any
   network endpoint.

### 3.3 Post-install first launch

Operator opens PowerShell (or the Start Menu shortcut) and runs:

```powershell
cd $env:LOCALAPPDATA\1c-ai-workbench
.\START_HERE.ps1
```

The guided wizard (see `docs/INSTALL_PROFILES.md`) presents four profiles.
For production onboarding the operator selects **Developer** or **Advanced AI**.

### 3.4 Environment validation

`scripts/01_check_env.ps1` runs automatically as the first wizard step.
It verifies:

- CPython 3.11 x64 is in PATH
- PowerShell execution policy allows scripts (or suggests per-process bypass)
- Workbench paths with spaces and Unicode characters resolve correctly
- `logs/` directory is writable

If any check fails, the wizard prints a specific error code (see Section 9)
and halts. The operator fixes the issue and reruns.

---

## 4. Phase 2 — VS Code and Continue

### 4.1 VS Code detection

The onboarding assistant checks for VS Code:

```text
where.exe code
```

| Result | Action |
|--------|--------|
| Found | Report version, proceed |
| Not found | Print download URL (`https://code.visualstudio.com/`) and instructions. Do NOT auto-install. |

VS Code installation is an explicit operator action. The workbench never
installs, updates, or configures VS Code.

### 4.2 Continue extension detection

The assistant checks for the Continue extension:

```powershell
code --list-extensions | Select-String "Continue.continue"
```

| Result | Action |
|--------|--------|
| Installed | Report version, proceed |
| Not installed | Print Marketplace URL and one-line install command. Do NOT auto-install. |

### 4.3 Continue profile connection

After VS Code + Continue are confirmed, the assistant offers to generate the
selected provider-neutral Continue profile via the existing generator:

```powershell
# Hosted BYOK/BYOM
.\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent -Preset zai -CheckOnly

# Or fully-local Agent mode
.\scripts\28_prepare_continue_profile.ps1 -Profile LocalAgent `
    -LocalAgentModel qwen2.5-coder:7b -CheckOnly
```

The generated YAML lands in `generated/continue/`. The operator manually
connects it to Continue per Continue documentation. The workbench does not
modify `~/.continue/` or any global Continue configuration.

---

## 5. Phase 3 — AI mode selection

The operator chooses exactly one AI mode. The choice is recorded in
`generated/onboarding-state.json` (see Section 8 state machine).

### 5.1 Mode A — Own cloud AI (BYOK)

| Property | Value |
|----------|-------|
| Provider | Any OpenAI-compatible API (Groq, OpenRouter, OpenAI, Azure OpenAI, etc.) |
| Key storage | Continue dotenv secret (`${{ secrets.PROVIDER_API_KEY }}`) |
| Network | Outbound HTTPS to provider endpoint |
| Data leaving machine | Prompts + retrieved context snippets |
| Local model | Ollama autocomplete model required by the current HostedAgent profile |

The onboarding assistant:

1. Asks which provider the operator uses.
2. Prints the exact dotenv file path and variable name.
3. Validates that the dotenv entry exists and is non-empty (value is never
   printed, logged, or transmitted).
4. Does NOT accept, store, or echo the key value.

### 5.2 Mode B — Corporate OpenAI-compatible endpoint

| Property | Value |
|----------|-------|
| Provider | Internal endpoint (e.g., `https://ai.corp.internal/v1`) |
| Key storage | Same Continue dotenv mechanism |
| Network | Outbound HTTPS to corporate endpoint only |
| Data leaving machine | Prompts + context to corporate network only |
| Compliance | Operator confirms corporate data-handling policy covers AI prompts |

Additional steps:

1. Assistant asks for the endpoint base URL.
2. Validates URL format (must be HTTPS, must not be `localhost` unless
   explicitly confirmed as local proxy).
3. Prints a corporate acknowledgment checkbox text for the operator to
   confirm internally.
4. Records endpoint URL (not key) in onboarding state.

### 5.3 Mode C — Local model only

| Property | Value |
|----------|-------|
| Provider | OpenAI-compatible loopback Agent endpoint plus Ollama autocomplete, or Offline Lite |
| Key storage | None |
| Network | Loopback only (127.0.0.1 / localhost / ::1); no outbound provider traffic |
| Data leaving machine | Nothing |
| Capabilities | LocalAgent: chat/edit/apply + MCP Agent + autocomplete; Offline Lite: autocomplete only |

The assistant:

1. Lets the operator choose LocalAgent or Offline Lite.
2. Checks Ollama autocomplete service and exact model tag (`ollama list`).
3. For LocalAgent, validates an OpenAI-compatible loopback `/v1` endpoint,
   checks `/v1/models` for the exact tool-capable model, and later proves one
   real Agent tool call in VS Code.
4. Validates `OLLAMA_HOST` and the Agent endpoint are loopback-only.
5. Generates LocalAgent or Offline Lite. Offline Lite prints the explicit
   warning that chat/edit/apply and MCP Agent calls are unavailable.

### 5.4 Mode change

The operator can change mode at any time by rerunning the profile generator
with a different `-Profile` flag. Previous profiles in `generated/continue/`
are overwritten only with `-Force`. The onboarding state records the mode
transition timestamp.

---

## 6. Secure key input and storage

### 6.1 Rules (MUST)

| # | Rule |
|---|------|
| K1 | Workbench generators never accept an API key value as a CLI argument or generated YAML literal; they accept only a validated secret name |
| K2 | Workbench scripts never print, log, hash, persist, or pass a key value to child probes; Continue alone resolves it for the selected provider |
| K3 | Key presence is validated by parsing the effective dotenv assignment only far enough to determine non-empty status; the value is held transiently, never returned, logged, or persisted |
| K4 | `.env` files are in `.gitignore` and `.continueignore` |
| K5 | The installer never creates, modifies, or deletes any `.env` file |
| K6 | Key rotation is the operator's responsibility; the workbench provides a "where is my key" reminder but never touches the file |

### 6.2 Supported secret resolution (Continue)

Per Continue documentation, secrets resolve in order:

1. `<workspace-root>/.env`
2. `<workspace-root>/.continue/.env`
3. `%USERPROFILE%/.continue/.env`

The onboarding assistant prints all three paths and lets the operator choose.
It does not create the parent directory or `.env` file and never edits a
global Continue directory — the operator creates and edits the file directly.

### 6.3 Key revocation guidance

After a pilot or key compromise:

1. Revoke the key at the provider dashboard.
2. Delete or empty the dotenv line.
3. Rerun `.\scripts\06_healthcheck.ps1` to confirm the workbench still
   functions for local search (it does — key absence only blocks AI mode).

---

## 7. 1C dump or repository selection

### 7.1 Source options

| Source | Description | Path convention |
|--------|-------------|-----------------|
| Configuration dump (XML/BSL) | Exported via 1C Designer → "Save configuration to files" | `C:\1c-ai-client\dump` |
| Git repository with EDT export | EDT project exported to XML | Any local path |
| Demo fixture | Committed test fixture in the repository | `tests/fixtures/` |

### 7.2 Validation

Before indexing, the assistant validates:

- The source path exists and is a directory.
- It contains at least one `Configuration.xml` (for dump) or `.bsl` file.
- Total size is within indexer limits (current: no hard limit, but >500 MB
  triggers a warning with estimated time).
- The source root is canonicalized and its resolved target is shown. A root
  junction may be accepted after explicit confirmation; nested reparse points
  that escape the resolved source root are rejected.

### 7.3 Indexing

```powershell
.\scripts\04_index_1c_dump.ps1 -WorkbenchRoot . -DumpRoot <path> -Force
```

The indexer creates `generated/index/source-mirror/.code-index/index.db`.
Indexing is idempotent: rerunning with `-Force` rebuilds from scratch;
without `-Force` it performs incremental update.

### 7.4 Index update

For ongoing work:

```powershell
.\scripts\04_index_1c_dump.ps1 -WorkbenchRoot . -DumpRoot <path>
```

Without `-Force`, the indexer detects changed files and updates incrementally.
The onboarding state records the last index timestamp and source path.

---

## 8. First-launch state machine

The onboarding assistant tracks progress through a deterministic state
machine. State is persisted in `generated/onboarding-state.json`.

### 8.1 States

```text
                    ┌─────────────────────────────────────────────────┐
                    │                                                 │
                    ▼                                                 │
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐ │
│ FRESH   │──▶│ ENV_OK  │──▶│ IDE_OK  │──▶│ MODE_SET│──▶│ KEY_OK  │ │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘ │
                    │             │             │             │       │
                    ▼             ▼             ▼             ▼       │
              ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐ │
              │ ENV_FAIL│   │ IDE_MISS│   │ MODE_   │   │ KEY_    │ │
              │         │   │         │   │ MISSING │   │ MISSING │ │
              └─────────┘   └─────────┘   └─────────┘   └─────────┘ │
                                                                 │   │
                                                                 ▼   │
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐ │
│ COMPLETE│◀──│ FIRST_  │◀──│ MCP_OK  │◀──│INDEX_OK │◀──│SOURCE_OK│ │
└─────────┘   │ ANSWER  │   └─────────┘   └─────────┘   └─────────┘ │
                    │                                                 │
                    ▼                                                 │
              ┌─────────┐                                            │
              │ CHANGE_ │────────────────────────────────────────────┘
              │ PROPOSED│  (operator rejects → back to FIRST_ANSWER)
              └─────────┘
                    │
                    ▼
              ┌─────────┐
              │ CHANGE_ │
              │ APPLIED │
              └─────────┘
```

### 8.2 State definitions

| State | Meaning | Entry condition | Exit condition |
|-------|---------|-----------------|----------------|
| `FRESH` | First launch, nothing configured | Installer completed | `01_check_env.ps1` passes |
| `ENV_OK` | Environment validated | All env checks green | VS Code + Continue detected |
| `ENV_FAIL` | Environment check failed | Any env check red | Operator fixes and reruns |
| `IDE_OK` | VS Code + Continue present | Both detected | AI mode selected |
| `IDE_MISS` | VS Code or Continue missing | Detection failed | Operator installs and reruns |
| `MODE_SET` | AI mode chosen | Operator selected A/B/C | Key validated (or N/A for local) |
| `MODE_MISSING` | No mode selected | Wizard reached mode step | Operator selects |
| `KEY_OK` | API key present (or N/A) | Dotenv entry exists / local mode | Source path validated |
| `KEY_MISSING` | Key required but absent | Dotenv check failed | Operator adds key |
| `SOURCE_OK` | 1C source validated | Path + content checks pass | Indexing completes |
| `INDEX_OK` | Index built | `index.db` exists, stats pass | MCP servers verified |
| `MCP_OK` | Code MCP + Help MCP respond | `initialize` + `tools/list` pass | First AI answer received |
| `FIRST_ANSWER` | Evidence-based answer delivered | AI cited file + line + confidence | Operator requests change or continues |
| `CHANGE_PROPOSED` | BSL edit suggested by AI | AI produced a diff | Operator confirms or rejects |
| `CHANGE_APPLIED` | Operator confirmed and applied | Diff accepted | Terminal state for this interaction |
| `COMPLETE` | Onboarding finished | First answer delivered | Terminal; operator can restart any phase |

### 8.3 State persistence schema

```json
{
  "$schema": "onboarding-state-v1",
  "version": "1.0.0",
  "current_state": "INDEX_OK",
  "ai_mode": "cloud_byok",
  "ai_provider": "zai",
  "ai_endpoint_url": "https://api.z.ai/api/paas/v4",
  "source_type": "dump",
  "source_path": "C:\\1c-ai-client\\dump",
  "last_index_utc": "2026-07-28T14:30:00Z",
  "last_index_stats": {
    "functions": 1240,
    "classes": 87,
    "variables": 3412,
    "calls": 1565
  },
  "mcp_code_ok": true,
  "mcp_help_ok": true,
  "first_answer_utc": null,
  "transitions": [
    {"from": "FRESH", "to": "ENV_OK", "utc": "2026-07-28T14:00:00Z"},
    {"from": "ENV_OK", "to": "IDE_OK", "utc": "2026-07-28T14:05:00Z"}
  ]
}
```

### 8.4 Invariants

- State only advances forward or resets to a named earlier state.
- No state transition occurs without an explicit operator action or a
  passing validation check.
- `CHANGE_APPLIED` is the only state where the onboarding assistant may modify
  a file, and only inside the canonical source mirror after explicit operator
  confirmation of a diff. Continue's general Apply button is not treated as
  this enforcement boundary until the controlled wrapper is implemented.
- The state file is in `generated/` and is preserved across upgrades.
- The state file never contains API keys, key hashes, or prompt content.

---

## 9. User error catalog

Every error has a stable code, a human-readable message (Russian + English),
a likely cause, and a recovery action. The onboarding assistant prints the
code so the operator can search documentation or paste it into a support
ticket.

### 9.1 Environment errors (E1xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E101 | Python не найден. Установите CPython 3.11 x64. | Python not found. Install CPython 3.11 x64. | CPython not in PATH | Install from python.org, restart terminal |
| E102 | Версия Python не поддерживается: {ver}. Нужна 3.11.x. | Unsupported Python version: {ver}. Need 3.11.x. | Wrong Python version | Install 3.11.x, check PATH order |
| E103 | Путь не удалось безопасно разрешить: {path} | Path could not be resolved safely: {path} | Invalid, inaccessible, or escaping path | Select an accessible local path and retry |
| E104 | Папка logs недоступна для записи. | Logs directory is not writable. | Permissions / antivirus | Grant Modify permission; check antivirus exclusions |
| E105 | PowerShell Execution Policy блокирует скрипты. | PowerShell Execution Policy blocks scripts. | Restricted policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| E106 | Недостаточно места на диске: {free} МБ (нужно {need} МБ). | Insufficient disk space: {free} MB (need {need} MB). | Disk full | Free space or choose another drive |

### 9.2 IDE errors (E2xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E201 | VS Code не найден. Установите вручную с code.visualstudio.com. | VS Code not found. Install manually from code.visualstudio.com. | VS Code not installed | Download and install |
| E202 | Расширение Continue не установлено. | Continue extension not installed. | Extension missing | `code --install-extension Continue.continue` |
| E203 | Версия Continue не поддерживает schema v1. Обновите расширение. | Continue version does not support schema v1. Update the extension. | Outdated Continue | Update via VS Code Extensions panel |

### 9.3 AI mode / key errors (E3xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E301 | API-ключ не найден. Создайте файл {path} и добавьте строку {VAR}=ваш_ключ. | API key not found. Create {path} and add line {VAR}=your_key. | Dotenv missing or empty | Create .env with key; do NOT commit |
| E302 | Ключ пустой. Строка {VAR}= найдена, но значение отсутствует. | Key is empty. Line {VAR}= found but value is missing. | Empty dotenv value | Add key value after `=` |
| E303 | Ollama не запущена. Установите и запустите Ollama. | Ollama is not running. Install and start Ollama. | Service not running | `ollama serve` or start Ollama app |
| E304 | Модель {model} не найдена. Выполните: ollama pull {model} | Model {model} not found. Run: ollama pull {model} | Model not pulled | Pull the exact model tag |
| E305 | OLLAMA_HOST указывает на удалённый адрес: {host}. Только loopback разрешён. | OLLAMA_HOST points to remote address: {host}. Only loopback allowed. | Non-loopback Ollama | Set to 127.0.0.1 or localhost |
| E306 | URL корпоративного endpoint не является HTTPS: {url} | Corporate endpoint URL is not HTTPS: {url} | HTTP endpoint | Use HTTPS or confirm local proxy |
| E307 | Локальный Agent endpoint должен быть loopback OpenAI-compatible URL с `/v1`: {url} | Local Agent endpoint must be a loopback OpenAI-compatible URL ending in `/v1`: {url} | Wrong host, scheme, or API path | Use `http://127.0.0.1:<port>/v1` and verify `/v1/models` |

### 9.4 Source / index errors (E4xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E401 | Папка выгрузки не найдена: {path} | Dump folder not found: {path} | Wrong path | Check path, re-export from 1C Designer |
| E402 | Configuration.xml не найден в выгрузке. | Configuration.xml not found in dump. | Incomplete export | Re-export: Designer → Save configuration to files |
| E403 | Выгрузка пуста (0 файлов). | Dump is empty (0 files). | Empty directory | Place actual export files |
| E404 | Индекс не создан. Запустите индексацию. | Index not created. Run indexing. | First run / index deleted | `.\scripts\04_index_1c_dump.ps1 -Force` |
| E405 | Индекс повреждён или несовместим. Пересоздайте с -Force. | Index corrupted or incompatible. Rebuild with -Force. | Version mismatch / corruption | Delete `generated/index/`, reindex |
| E406 | Вложенная ссылка выходит за границы выгрузки: {path}. | Nested link escapes the resolved source root: {path}. | Reparse-point traversal in source | Remove the escaping link or choose a contained source |

### 9.5 MCP errors (E5xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E501 | bsl-indexer.exe не найден. Запустите setup.ps1 или соберите из исходников. | bsl-indexer.exe not found. Run setup.ps1 or build from source. | Binary missing | `.\scripts\setup.ps1` or `.\scripts\03_build_bsl_indexer.ps1` |
| E502 | Code MCP не отвечает на initialize. | Code MCP does not respond to initialize. | Binary crash / wrong path | Check `logs/`, verify binary runs: `bsl-indexer --help` |
| E503 | Help MCP не отвечает. Проверьте Python venv и HELP_INDEX_MODE. | Help MCP does not respond. Check Python venv and HELP_INDEX_MODE. | venv missing / wrong mode | Recreate venv, set `HELP_INDEX_MODE=readonly` |
| E504 | Help MCP база данных отсутствует. Сначала проиндексируйте справку. | Help MCP database missing. Index the help first. | No .hbk indexed | Run help indexing per docs |
| E505 | MCP tools/list вернул пустой список. | MCP tools/list returned empty list. | Index empty / binary mismatch | Reindex, verify binary version matches index |

### 9.6 AI answer errors (E6xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E601 | AI-провайдер вернул HTTP {code}. Проверьте ключ и доступность модели. | AI provider returned HTTP {code}. Check key and model availability. | Auth / quota / network | Verify key, check provider status page |
| E602 | AI ответ не содержит evidence (файл/строка). Ответ отклонён. | AI answer lacks evidence (file/line). Answer rejected. | Model hallucination | Rephrase query; check MCP connection |
| E603 | Тайм-аут ответа AI ({sec} сек). Проверьте сеть. | AI response timeout ({sec} s). Check network. | Network / provider slow | Retry; check firewall/proxy |

### 9.7 Change proposal errors (E7xx)

| Code | Message (RU) | Message (EN) | Cause | Recovery |
|------|-------------|-------------|-------|----------|
| E701 | Файл для изменения не найден: {path} | Target file not found: {path} | File moved/deleted | Reindex, verify path |
| E702 | Файл изменён с момента индексации. Переиндексируйте. | File modified since indexing. Reindex. | Stale index | Rerun incremental index |
| E703 | Изменение отклонено оператором. | Change rejected by operator. | Operator pressed reject | No action needed |

---

## 10. MCP verification

### 10.1 Code MCP (bsl-indexer)

The onboarding assistant performs a stdio MCP handshake:

1. Spawn `bsl-indexer.exe serve --path onec=<source-mirror> --transport stdio`
   with `CODE_INDEX_HOME=<generated/code-index-home>`.
2. Send `initialize` request. Expect `capabilities.tools` in response.
3. Send `tools/list`. Expect at least: `search_text`, `find_definition`,
   `get_body`, `get_callers`, `get_callees`, `meta_info`, `form_info`,
   `stats`.
4. Send a `stats` call. Expect non-zero function count.
5. Kill the process.

Pass criteria: all five steps succeed within 30 seconds.

### 10.2 Help MCP (Python)

1. Activate project `.venv`.
2. Set `HELP_INDEX_MODE=readonly`.
3. Spawn Help MCP server via stdio.
4. Send `initialize`. Expect response.
5. Send `tools/list`. Expect `search_help` present; `reindex_help` and
   `export_help_browser` MUST be absent (readonly mode).
6. Send `search_help` with a known topic. Expect non-empty result.
7. Kill the process.

Pass criteria: all seven steps succeed; mutating tools absent.

### 10.3 Failure handling

If either MCP fails, the assistant:

- Prints the specific error code (E5xx).
- Suggests the recovery action.
- Does NOT advance the state machine.
- Offers to retry after the operator fixes the issue.

---

## 11. First evidence-based AI answer

### 11.1 Prompt template

The onboarding assistant suggests a first query from the role-based packs:

```text
Найди процедуру РассчитатьСумму в выгрузке.
Назови конкретный файл, строку, тело процедуры и уверенность.
Если точного совпадения нет — скажи прямо.
```

### 11.2 Evidence requirements

A valid first answer MUST contain:

| Field | Example |
|-------|---------|
| File path | `CommonModules/УправлениеТорговлей/Ext/Module.bsl` |
| Line or identifier | Line 142 / `Процедура РассчитатьСумму` |
| Code fragment | First 5 lines of the procedure body |
| Confidence | "Точное совпадение" / "Похожий результат: ..." |
| Verification hint | "Откройте файл в VS Code, Ctrl+G → строка 142" |

If the AI cannot find the symbol, it MUST say "Не найдено" explicitly.
Substituting a similar name without disclosure is a spec violation.

### 11.3 State transition

On receiving a valid evidence-based answer: `MCP_OK` → `FIRST_ANSWER`.
The assistant records only the timestamp and a generated correlation ID. Prompt
and response text are excluded from the state file.

---

## 12. BSL change proposal and diff review

### 12.1 Change proposal flow

1. Operator asks the AI to modify a BSL file (e.g., "Добавь проверку на
   ноль в РассчитатьСумму").
2. AI produces a unified diff or a before/after code block.
3. The onboarding assistant renders the diff with syntax highlighting and
   canonicalizes every target under `generated/index/source-mirror`. Continue's
   built-in diff view may be used for display, but is not the security gate.
4. Operator sees: file path, line range, removed lines (red), added lines
   (green), and a plain-language summary of the change.

### 12.2 Confirmation gate (MUST)

| Rule | Description |
|------|-------------|
| C1 | No file is modified without explicit confirmation through the controlled onboarding gate; a raw Continue "Apply" click alone is insufficient |
| C2 | The diff is shown BEFORE confirmation; no "apply then show" |
| C3 | The operator can reject at any time; rejection returns to `FIRST_ANSWER` state |
| C4 | After apply, the assistant suggests re-running the indexer incrementally |
| C5 | The original file content is recoverable from a pre-apply hash-locked backup or Git; `Ctrl+Z` alone is not the recovery contract |

### 12.3 What is NOT allowed

| Prohibited action | Reason |
|-------------------|--------|
| Auto-apply without diff display | Violates C2 |
| Batch-apply multiple files without per-file confirmation | Violates C1 |
| Write to any path outside the indexed source mirror | Scope violation |
| Write to a live 1C database | P1: read-only by default |
| Execute `ibcmd` or `live-1c-bridge` commands | Disabled by default; separate security review required |

---

## 13. Explicit boundary: no automatic changes to live 1C

This is a non-negotiable production invariant.

### 13.1 Statement

> The 1C AI Workbench production onboarding path NEVER writes to, modifies,
> deletes, or executes commands against a live 1C information base.

### 13.2 Enforcement

| Control | Implementation |
|---------|----------------|
| `live-1c-bridge` MCP server | Disabled by default in `opencode.jsonc`; not registered in Continue profiles |
| `ibcmd-bridge` MCP server | Disabled by default; `IBCMD_ALLOW_WRITE=0` enforced |
| Installer | Does not include 1C binaries, COM registration, or database connection strings |
| Onboarding assistant | Never asks for 1C server address, database credentials, or connection string |
| Security policy | `configs/security-policy.example.json` → `live_bridges_disabled_by_default: true` |
| Documentation | `docs/SECURITY_NOTES.md` → "Do not test on a live production 1C database" |

### 13.3 What the operator CAN do (outside onboarding)

- Manually enable `live-1c-bridge` in a disposable test environment after
  separate security review.
- Use `ibcmd` with explicit write permission in an isolated copy.
- These are post-onboarding, out-of-scope, and require documented approval.

---

## 14. Privacy and log-redaction requirements

### 14.1 Data classification

| Data class | Examples | Handling |
|------------|----------|----------|
| Secret | API keys, tokens, passwords | Never logged, never printed, never stored in state file |
| Sensitive | 1C dump content, BSL source code, business logic | Stays local except snippets explicitly sent by Continue in an operator-initiated provider query |
| Operational | Index stats, MCP handshake results, error codes, timestamps | Logged to `logs/`; safe for support tickets |
| Public | Documentation, version numbers, OS version | No restriction |

### 14.2 Log redaction rules (MUST)

| # | Rule |
|---|------|
| L1 | No log line may contain an API key, token, password, or secret value |
| L2 | Routine logs contain no BSL source content; an explicit diagnostic export requires separate operator consent and redaction |
| L3 | Error messages may contain file paths and error codes but not file contents |
| L4 | The onboarding state file never contains prompt text, AI response text, or key material |
| L5 | MCP stdio probe processes receive no secret values in arguments or environment beyond what the MCP server itself requires |
| L6 | If a log line would contain a secret, it is replaced with `[REDACTED:<field-name>]` |
| L7 | `gitleaks` and pre-commit hooks prevent accidental secret commits |

### 14.3 Network privacy

| Mode | Network calls | Destination |
|------|--------------|-------------|
| Cloud BYOK | Workbench-owned traffic: none; Continue sends operator-initiated AI queries | Operator-chosen provider |
| Corporate | Workbench-owned traffic: none; Continue sends operator-initiated AI queries | Corporate endpoint |
| Local | Workbench-owned traffic: loopback only | 127.0.0.1 / localhost / ::1 |
| All modes | Workbench processes: zero telemetry, auto-update, and crash reporting | VS Code/Continue network behavior is measured and configured separately |

### 14.4 Operator privacy checklist

Printed at the end of onboarding:

```text
☐ API-ключ хранится только в локальном .env и не попадает в Git
☐ Выгрузка 1С не отправляется никуда, кроме выбранного AI-провайдера
☐ Логи в logs/ не содержат ключей и исходного кода
☐ Живая база 1С не подключена и не изменяется
☐ Телеметрия отсутствует
```

---

## 15. Diagnostics, recovery, update, and uninstall

### 15.1 Diagnostics

| Tool | Command | Output |
|------|---------|--------|
| Healthcheck | `.\scripts\06_healthcheck.ps1` | `generated/reports/readiness-report.md` + `.html` |
| Environment | `.\scripts\01_check_env.ps1` | Console output with pass/fail per check |
| MCP probe | `python .\scripts\30_probe_mcp_stdio.py` | JSON handshake result |
| Index stats | `bsl-indexer.exe stats --path <mirror>` | Function/class/variable/call counts |
| Evidence pack | See `docs/RECOVERY.md` Section 7 | ZIP with logs, reports, git state |

### 15.2 Recovery

Recovery follows `docs/RECOVERY.md`. The onboarding assistant integrates
the six-check model:

1. `binary exists` → E501
2. `index exists` → E404
3. `logs writable` → E104
4. `stats command` → E405
5. `query smoke` → E505
6. `mcp help` → E502

Each check maps to an error code and recovery action from Section 9.

### 15.3 Update

| Scenario | Behavior |
|----------|----------|
| Minor/patch upgrade | Run newer installer. `UsePreviousAppDir=yes` upgrades in place. `generated/` and `logs/` preserved. |
| Major upgrade | Same mechanism. Release notes describe breaking changes. |
| Downgrade | Rejected by default. `/ALLOWDOWNGRADE=1` requires explicit operator action and is logged. |
| Index compatibility | If `bsl-indexer` version changes, incremental index may fail. Assistant suggests `-Force` rebuild. |

### 15.4 Rollback

If an upgrade breaks the workbench:

1. Run the previous signed installer with `/ALLOWDOWNGRADE=1`.
2. `generated/` and `logs/` are preserved (user data).
3. Rerun healthcheck. If index is incompatible, rebuild with `-Force`.
4. The onboarding state file is preserved; the assistant detects the
   version change and re-validates MCP handshake.

### 15.5 Uninstall

| Component | Uninstall behavior |
|-----------|-------------------|
| Application files | Removed by Inno Setup |
| Start Menu / desktop shortcuts | Removed |
| Registry entries | Removed |
| `.venv` and Python cache | Removed |
| `generated/` (indexes, reports, state) | **Preserved** — operator deletes manually |
| `logs/` | **Preserved** — operator deletes manually |
| `.env` files | **Never touched** — operator deletes manually |
| VS Code / Continue / Ollama | **Never touched** — not installed by workbench |

---

## 16. Components and files for implementation

This section lists the concrete artifacts needed to implement this spec.
None of these exist yet; they are design outputs for subsequent PRs.

### 16.1 New files to create

| File | Purpose |
|------|---------|
| `scripts/31_onboarding_assistant.ps1` | Main onboarding wizard (state machine driver) |
| `scripts/32_validate_ai_mode.ps1` | AI mode selection + key presence validation |
| `scripts/33_verify_mcp_handshake.ps1` | Automated Code MCP + Help MCP stdio probe |
| `scripts/34_first_answer_check.ps1` | Guided first query + evidence validation |
| `scripts/35_propose_bsl_change.ps1` | Diff rendering + confirmation gate |
| `scripts/36_diagnose.ps1` | Unified diagnostics orchestrator (wraps healthcheck + MCP probe + env check + Continue config preflight) |
| `scripts/37_diagnose_continue_config.ps1` | Focused Continue 2.0.0 config preflight (read-only; invoked by 36 as sub-component) |
| `configs/onboarding-state.schema.json` | JSON Schema for `generated/onboarding-state.json` |
| `configs/error-catalog.json` | Machine-readable error catalog (code → message RU/EN → recovery) |
| `docs/PRODUCTION_ONBOARDING_SPEC.md` | This document |
| `docs/PRODUCTION_ACCEPTANCE_MATRIX.md` | Acceptance criteria companion |
| `tests/test_onboarding_state.py` | State machine transition tests |
| `tests/test_error_catalog.py` | Error catalog completeness and format tests |
| `tests/test_log_redaction.py` | Verify no secrets leak into log patterns |

### 16.2 Existing files to reference (NOT modify)

| File | Role in onboarding |
|------|-------------------|
| `START_HERE.ps1` | Entry point; wizard profile selection |
| `scripts/01_check_env.ps1` | Environment validation (E1xx) |
| `scripts/04_index_1c_dump.ps1` | Indexing (E4xx) |
| `scripts/06_healthcheck.ps1` | Six-check health model |
| `scripts/28_prepare_continue_profile.ps1` | Continue profile generation (GLM 5.2 owns; do not modify) |
| `scripts/29_validate_continue_profile.py` | Profile validation (GLM 5.2 owns; do not modify) |
| `scripts/30_probe_mcp_stdio.py` | MCP stdio probe (GLM 5.2 owns; do not modify) |
| `configs/install-profiles.json` | Profile metadata |
| `configs/security-policy.example.json` | Security baseline |
| `docs/RECOVERY.md` | Recovery procedures |
| `docs/WINDOWS_EXE_INSTALLER.md` | Installer contract |
| `docs/CONTINUE_THIN_CLIENT.md` | Continue profile architecture |
| `docs/API_KEY_SETUP.md` | Key handling guidance |

### 16.3 Integration points

| Integration | Direction | Contract |
|-------------|-----------|----------|
| GLM 5.2 provider-neutral BYOK/BYOM | Consumes | Onboarding reads generated profiles; does not generate them |
| Continue extension | External | Onboarding detects and guides; does not install or configure |
| Ollama | External | Onboarding detects and validates; does not install or pull models |
| Inno Setup installer | Upstream | Onboarding assumes installer completed; does not invoke it |
| Release/signing workflows | Out of scope | No changes |

---

## 17. MUST / SHOULD / LATER

### 17.1 MUST (production-blocking)

| # | Requirement |
|---|-------------|
| M1 | State machine persists across sessions and survives upgrade |
| M2 | Every error has a stable code, RU+EN message, and recovery action |
| M3 | No API key value appears in any log, state file, or console output |
| M4 | No write to live 1C database at any onboarding stage |
| M5 | BSL change requires explicit diff display + operator confirmation |
| M6 | MCP verification passes before first AI answer is attempted |
| M7 | Clean-Windows install requires no admin privileges |
| M8 | Uninstall preserves `generated/` and `logs/` |
| M9 | Downgrade rejected by default |
| M10 | LocalAgent and Offline Lite work with the network adapter disabled; Workbench traffic remains loopback-only |
| M11 | `.env` files never created, modified, or deleted by workbench scripts |
| M12 | Error catalog is machine-readable and versioned |

### 17.2 SHOULD (quality-improving, not release-blocking)

| # | Requirement |
|---|-------------|
| S1 | Onboarding assistant offers to open the readiness report in browser |
| S2 | First-answer check suggests role-specific queries (lead/dev/partner) |
| S3 | Diagnostics produces a one-click evidence ZIP for support tickets |
| S4 | State machine supports "resume from last state" after interruption |
| S5 | AI mode change prints a clear summary of what changes (network, capabilities) |
| S6 | Index update shows progress percentage for large dumps |
| S7 | Error messages include a "learn more" URL to the relevant docs section |
| S8 | Onboarding completion prints a privacy checklist |

### 17.3 LATER (post-publication)

| # | Requirement |
|---|-------------|
| L1 | GUI onboarding wizard (WPF/WebView) replacing PowerShell prompts |
| L2 | Automatic VS Code / Continue installation with operator consent |
| L3 | Ollama model auto-pull with progress bar |
| L4 | Multi-configuration support (multiple 1C dumps in one workbench) |
| L5 | Cloud sync of onboarding state (opt-in, encrypted) |
| L6 | Interactive BSL diff with inline accept/reject per hunk |
| L7 | AI answer quality scoring and feedback loop |
| L8 | Corporate SSO integration for AI endpoint authentication |
| L9 | Portable ZIP distribution alongside installer |
| L10 | Log rotation and size limits |

---

## 18. Acceptance summary

Full acceptance criteria are in `docs/PRODUCTION_ACCEPTANCE_MATRIX.md`.
This spec is considered implemented when:

1. All M-items pass on clean Windows 10 and Windows 11.
2. Error catalog covers every failure path exercised by the state machine.
3. No secret material appears in any log or state artifact (verified by
   `tests/test_log_redaction.py`).
4. MCP handshake passes for both Code MCP and readonly Help MCP.
5. First evidence-based answer contains file, line, fragment, and confidence.
6. BSL change proposal shows diff and requires confirmation.
7. Uninstall preserves user data; downgrade is rejected by default.

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| BYOK | Bring Your Own Key — operator supplies their own AI provider API key |
| BYOM | Bring Your Own Model — operator supplies their own model endpoint |
| Code MCP | `bsl-indexer` MCP server providing structural search over 1C BSL code |
| Help MCP | Python MCP server providing FTS5 search over 1C Syntax Helper |
| Dump | XML/BSL export of a 1C configuration via Designer |
| Evidence | File path + line/identifier + code fragment + confidence in an AI answer |
| Onboarding state | JSON file tracking the operator's progress through first-launch setup |
| Source mirror | Local copy of the indexed 1C dump under `generated/index/source-mirror` |
| Stdio transport | MCP communication over stdin/stdout (no network) |

## Appendix B: Related documents

| Document | Relationship |
|----------|-------------|
| `docs/PRODUCTION_ACCEPTANCE_MATRIX.md` | Acceptance criteria for this spec |
| `docs/CONTINUE_THIN_CLIENT.md` | Continue profile architecture (upstream) |
| `docs/WINDOWS_EXE_INSTALLER.md` | Installer contract (upstream) |
| `docs/RECOVERY.md` | Recovery procedures (referenced) |
| `docs/SECURITY_NOTES.md` | Security boundary (referenced) |
| `docs/API_KEY_SETUP.md` | Key handling (referenced) |
| `docs/PRODUCTION_READINESS_2026-07-18.md` | Current readiness status (context) |
| `docs/RELEASE_CONTRACT_V1.md` | Release signing contract (out of scope) |
