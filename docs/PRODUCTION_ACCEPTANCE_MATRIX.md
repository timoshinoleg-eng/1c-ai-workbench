# Production Acceptance Matrix

> Version: 1.0-draft
> Status: Design — not implemented
> Companion to: `docs/PRODUCTION_ONBOARDING_SPEC.md`
> Base commit: `538db97` (Draft PR #3 head)

This matrix defines pass/fail acceptance criteria for every production
onboarding stage. Each criterion has a unique ID, a verification method,
and a priority tier (MUST / SHOULD / LATER).

---

## 1. How to read this matrix

| Column | Meaning |
|--------|---------|
| ID | Stable criterion identifier (e.g., `CW-01`) |
| Criterion | What must be true |
| Verification | How to prove it (manual step, script, or test) |
| Tier | MUST = release-blocking; SHOULD = quality gate; LATER = post-publication |
| Evidence | What artifact proves pass (screenshot, log, report file) |

Status values: `PASS` / `FAIL` / `NOT RUN` / `WAIVED` (with justification).

A production release requires every MUST criterion to be `PASS` on both
clean Windows 10 x64 and clean Windows 11 x64.

---

## 2. Clean-Windows acceptance (CW)

These criteria are verified on a fresh VM with no developer tools, no prior
workbench installation, and no cached artifacts.

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| CW-01 | Installer runs without UAC elevation prompt | Double-click signed `.exe`; observe no shield dialog | MUST | Screenshot + screen recording |
| CW-02 | Installer completes silently with `/VERYSILENT /SUPPRESSMSGBOXES` | Run from cmd; exit code 0 | MUST | Console output |
| CW-03 | Install location is `%LOCALAPPDATA%\1c-ai-workbench` | Check path after install | MUST | `dir` output |
| CW-04 | No files written outside `%LOCALAPPDATA%` (except Start Menu shortcut) | Process Monitor trace during install | MUST | ProcMon `.pml` |
| CW-05 | `bsl-indexer.exe` is present and reports `code-index 0.45.0` | `bsl-indexer.exe --version` | MUST | Console output |
| CW-06 | Python lock file and offline wheelhouse are present | Check `requirements-production.lock` + `offline-wheelhouse/` | MUST | `dir` output |
| CW-07 | `START_HERE.ps1` launches without error | Run in PowerShell 5.1 | MUST | Console output |
| CW-08 | `01_check_env.ps1` detects missing CPython and prints E101 | Run on VM without Python | MUST | Console output with E101 |
| CW-09 | After installing CPython 3.11, `01_check_env.ps1` passes | Reinstall Python, rerun | MUST | Console output all green |
| CW-10 | No network calls during install (offline install) | ProcMon + Wireshark; zero outbound connections | MUST | Capture files |
| CW-11 | Installer SHA-256 matches published checksum | `Get-FileHash` vs `checksums.txt` | MUST | Hash output |
| CW-12 | Authenticode signature is valid (`signtool verify /pa /v`) | Run signtool | MUST | Console output |
| CW-13 | RFC 3161 timestamp is present and valid | `signtool verify /pa /v` timestamp section | MUST | Console output |
| CW-14 | SmartScreen behavior is recorded (warning or pass) | Launch on clean VM with SmartScreen enabled | MUST | Screenshot + text |
| CW-15 | No Cyrillic characters in default install path | Inspect `%LOCALAPPDATA%` path | MUST | Path string |

---

## 3. Environment validation acceptance (EV)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| EV-01 | CPython 3.11 x64 detected when in PATH | `01_check_env.ps1` | MUST | Console |
| EV-02 | Wrong Python version (3.10, 3.12) rejected with E102 | Install 3.12, run check | MUST | Console with E102 |
| EV-03 | Cyrillic path rejected with E103 | Install to `C:\Пользователь\` | MUST | Console with E103 |
| EV-04 | Space in path rejected with E103 | Install to `C:\My Tools\` | MUST | Console with E103 |
| EV-05 | Read-only `logs/` rejected with E104 | `icacls logs /deny Users:W`, run check | MUST | Console with E104 |
| EV-06 | Restricted Execution Policy detected with E105 | `Set-ExecutionPolicy Restricted`, run | MUST | Console with E105 |
| EV-07 | Low disk space detected with E106 | Fill disk to <500 MB free, run | SHOULD | Console with E106 |
| EV-08 | All checks pass on a compliant system | Standard clean VM after Python install | MUST | All green |

---

## 4. IDE detection acceptance (ID)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| ID-01 | VS Code detected when installed | `where.exe code` succeeds | MUST | Console |
| ID-02 | VS Code absence prints E201 with download URL | Run on VM without VS Code | MUST | Console with E201 |
| ID-03 | Continue extension detected when installed | `code --list-extensions` contains `Continue.continue` | MUST | Console |
| ID-04 | Continue absence prints E202 with install command | Run without extension | MUST | Console with E202 |
| ID-05 | Workbench does NOT auto-install VS Code | Observe: no installer launched | MUST | ProcMon trace |
| ID-06 | Workbench does NOT auto-install Continue | Observe: no extension install | MUST | ProcMon trace |
| ID-07 | Continue version supporting schema v1 detected | Check extension version ≥ threshold | SHOULD | Console |

---

## 5. AI mode selection acceptance (AM)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| AM-01 | Cloud BYOK mode records provider in state file | Select mode A, check `onboarding-state.json` | MUST | JSON content |
| AM-02 | Corporate mode records endpoint URL (not key) | Select mode B, check state | MUST | JSON content |
| AM-03 | Corporate mode rejects non-HTTPS URL with E306 | Enter `http://ai.corp/v1` | MUST | Console with E306 |
| AM-04 | Local mode records no provider, no endpoint | Select mode C, check state | MUST | JSON content |
| AM-05 | Local mode warns about autocomplete-only limitation | Observe warning text | MUST | Console |
| AM-06 | Mode change overwrites previous mode in state | Switch A→C, check state | MUST | JSON content |
| AM-07 | Mode change does not delete existing `.env` | Switch modes, verify `.env` intact | MUST | File check |
| AM-08 | State file never contains API key value | Grep state file for key patterns | MUST | Grep output (empty) |

---

## 6. Key storage acceptance (KS)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| KS-01 | Key presence validated without reading value | Check script logic: only line existence tested | MUST | Code review |
| KS-02 | Missing key prints E301 with exact file path and variable name | Remove `.env`, run validation | MUST | Console with E301 |
| KS-03 | Empty key value prints E302 | Create `.env` with `KEY=`, run | MUST | Console with E302 |
| KS-04 | Key value never appears in console output | Run all onboarding steps, capture stdout+stderr, grep for key pattern | MUST | Grep output (empty) |
| KS-05 | Key value never appears in `logs/` | Run all steps, grep `logs/` recursively | MUST | Grep output (empty) |
| KS-06 | Key value never appears in `generated/onboarding-state.json` | Inspect state file | MUST | File content |
| KS-07 | `.env` is in `.gitignore` | Check `.gitignore` | MUST | File content |
| KS-08 | `.env` is in `.continueignore` | Check `.continueignore` | MUST | File content |
| KS-09 | Installer does not create any `.env` file | Install on clean VM, search for `.env` | MUST | `dir /s /b *.env` (empty) |
| KS-10 | Uninstaller does not delete `.env` files | Uninstall, verify `.env` still exists | MUST | File check |
| KS-11 | `gitleaks` pre-commit hook blocks accidental key commit | Stage a file with `sk-...`, attempt commit | MUST | Hook rejection output |

---

## 7. Source and index acceptance (SI)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| SI-01 | Valid dump with `Configuration.xml` accepted | Point to demo fixture, run validation | MUST | Console pass |
| SI-02 | Missing path prints E401 | Point to nonexistent dir | MUST | Console with E401 |
| SI-03 | Empty directory prints E403 | Point to empty dir | MUST | Console with E403 |
| SI-04 | Directory without `Configuration.xml` prints E402 | Point to dir with random files | MUST | Console with E402 |
| SI-05 | Junction/symlink in path prints E406 | Create junction, point to it | MUST | Console with E406 |
| SI-06 | Indexing creates `index.db` | Run `04_index_1c_dump.ps1 -Force` | MUST | File exists |
| SI-07 | `bsl-indexer stats` returns non-zero counts | Run stats on fresh index | MUST | JSON output |
| SI-08 | Incremental reindex preserves existing data | Modify one file, reindex without `-Force` | MUST | Stats delta |
| SI-09 | Full reindex with `-Force` rebuilds from scratch | Run with `-Force`, compare stats | MUST | Stats match |
| SI-10 | Index state recorded in `onboarding-state.json` | Check `last_index_utc` and stats | MUST | JSON content |
| SI-11 | Large dump (>500 MB) triggers size warning | Point to large dump | SHOULD | Console warning |

---

## 8. MCP verification acceptance (MV)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| MV-01 | Code MCP responds to `initialize` within 30 s | `30_probe_mcp_stdio.py` or equivalent | MUST | JSON response |
| MV-02 | Code MCP `tools/list` includes all required tools | Check response for 8+ tools | MUST | JSON response |
| MV-03 | Code MCP `stats` returns non-zero function count | Call stats tool | MUST | JSON response |
| MV-04 | Help MCP responds to `initialize` | Stdio probe | MUST | JSON response |
| MV-05 | Help MCP `tools/list` includes `search_help` | Check response | MUST | JSON response |
| MV-06 | Help MCP `tools/list` does NOT include `reindex_help` | Check response (readonly mode) | MUST | JSON response |
| MV-07 | Help MCP `tools/list` does NOT include `export_help_browser` | Check response (readonly mode) | MUST | JSON response |
| MV-08 | Help MCP `search_help` returns non-empty for known topic | Call with test query | MUST | JSON response |
| MV-09 | Missing binary prints E501 | Rename `bsl-indexer.exe`, run probe | MUST | Console with E501 |
| MV-10 | Corrupt index prints E405 | Truncate `index.db`, run stats | MUST | Console with E405 |
| MV-11 | MCP failure does NOT advance state machine | Fail MCP, check state stays at `INDEX_OK` | MUST | State file |
| MV-12 | MCP probe completes within 30 s total | Time the full probe | SHOULD | Timing output |

---

## 9. First AI answer acceptance (FA)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| FA-01 | AI answer contains file path | Inspect response for path pattern | MUST | Screenshot / text |
| FA-02 | AI answer contains line number or identifier | Inspect response | MUST | Screenshot / text |
| FA-03 | AI answer contains code fragment | Inspect response for code block | MUST | Screenshot / text |
| FA-04 | AI answer contains confidence statement | Inspect response for confidence wording | MUST | Screenshot / text |
| FA-05 | AI answer contains verification hint | Inspect response for "how to check" | SHOULD | Screenshot / text |
| FA-06 | Nonexistent symbol returns explicit "Не найдено" | Query `НесуществующийМетодXYZ` | MUST | Screenshot / text |
| FA-07 | Similar-name substitution without disclosure is a FAIL | Query `РассчитатьСумма` when only `РассчитатьСумму` exists | MUST | Screenshot / text |
| FA-08 | State transitions to `FIRST_ANSWER` after valid answer | Check state file | MUST | JSON content |
| FA-09 | Provider HTTP error prints E601 with code | Use invalid key, query | MUST | Console with E601 |
| FA-10 | Timeout prints E603 | Block network, query | SHOULD | Console with E603 |

---

## 10. BSL change proposal acceptance (BC)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| BC-01 | AI produces a diff for a requested BSL change | Ask "add null check to procedure X" | MUST | Screenshot |
| BC-02 | Diff is displayed BEFORE any file modification | Observe sequence: diff shown → prompt → apply | MUST | Screen recording |
| BC-03 | Diff shows file path, line range, removed/added lines | Inspect diff rendering | MUST | Screenshot |
| BC-04 | Operator can reject the change | Press reject / `n` | MUST | State returns to `FIRST_ANSWER` |
| BC-05 | Rejection does NOT modify any file | Check file hash before/after reject | MUST | Hash comparison |
| BC-06 | Confirmation applies the change to the source mirror file | Accept, verify file content changed | MUST | File diff |
| BC-07 | After apply, assistant suggests incremental reindex | Observe prompt | SHOULD | Console |
| BC-08 | Original content is recoverable (git diff or Ctrl+Z) | Check `git diff` shows the change | MUST | Git output |
| BC-09 | No batch apply without per-file confirmation | Request multi-file change; observe per-file gate | MUST | Screen recording |
| BC-10 | No write outside indexed source mirror | Attempt path traversal in change target | MUST | Error E701 |
| BC-11 | State transitions to `CHANGE_PROPOSED` then `CHANGE_APPLIED` | Check state file transitions | MUST | JSON content |

---

## 11. Live 1C boundary acceptance (LB)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| LB-01 | `live-1c-bridge` is not registered in any Continue profile | Grep `generated/continue/*.yaml` | MUST | Grep output (empty) |
| LB-02 | `ibcmd-bridge` is not registered in any Continue profile | Grep `generated/continue/*.yaml` | MUST | Grep output (empty) |
| LB-03 | `IBCMD_ALLOW_WRITE` is `0` in all configs | Grep configs | MUST | Grep output |
| LB-04 | Installer does not include 1C binaries | Inspect installer payload / Inno script | MUST | File list |
| LB-05 | Onboarding never asks for 1C server address | Run full onboarding, observe prompts | MUST | Screen recording |
| LB-06 | Onboarding never asks for database credentials | Run full onboarding, observe prompts | MUST | Screen recording |
| LB-07 | No MCP server connects to a 1C database during onboarding | ProcMon + network trace | MUST | Capture files |
| LB-08 | `security-policy.example.json` has `live_bridges_disabled_by_default: true` | Inspect file | MUST | File content |

---

## 12. Privacy and log-redaction acceptance (PR)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| PR-01 | No API key in any file under `logs/` | `Select-String -Path logs\* -Pattern "sk-\|api_key\|token\|password\|secret"` | MUST | Empty output |
| PR-02 | No API key in `generated/onboarding-state.json` | Inspect file | MUST | File content |
| PR-03 | No API key in console output during full onboarding | Capture all stdout+stderr, grep | MUST | Empty grep |
| PR-04 | No BSL source line >80 chars in logs | Grep logs for long code patterns | MUST | Empty output |
| PR-05 | Error messages contain paths and codes, not file contents | Review all E-codes in catalog | MUST | Catalog review |
| PR-06 | MCP probe processes receive no secrets in args/env | Inspect probe script logic | MUST | Code review |
| PR-07 | Redacted fields show `[REDACTED:<name>]` not raw value | Trigger a log line that would contain a secret | MUST | Log line |
| PR-08 | `gitleaks` passes on the repository | `gitleaks detect` | MUST | Exit code 0 |
| PR-09 | Zero telemetry / zero auto-update network calls | Wireshark during full onboarding (all modes) | MUST | Capture (zero outbound except AI queries in cloud mode) |
| PR-10 | Privacy checklist printed at onboarding completion | Observe final output | SHOULD | Console |

---

## 13. Update acceptance (UP)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| UP-01 | Newer version upgrades in place (`UsePreviousAppDir=yes`) | Install v1, then v2; check path | MUST | File check |
| UP-02 | `generated/` preserved after upgrade | Compare before/after | MUST | Dir listing |
| UP-03 | `logs/` preserved after upgrade | Compare before/after | MUST | Dir listing |
| UP-04 | `onboarding-state.json` preserved after upgrade | Compare before/after | MUST | File content |
| UP-05 | `.env` files preserved after upgrade | Compare before/after | MUST | File check |
| UP-06 | Managed application files replaced after upgrade | Check binary version | MUST | `bsl-indexer --version` |
| UP-07 | Downgrade rejected by default | Install v2, then v1 without flag | MUST | Installer rejection message |
| UP-08 | Downgrade with `/ALLOWDOWNGRADE=1` succeeds | Install v2, then v1 with flag | MUST | Install completes |
| UP-09 | Post-upgrade healthcheck passes | Run `06_healthcheck.ps1` after upgrade | MUST | All green |
| UP-10 | Post-upgrade MCP handshake passes | Run probe after upgrade | MUST | JSON pass |
| UP-11 | Index incompatibility detected and rebuild suggested | Upgrade indexer version, run stats | SHOULD | Console suggestion |

---

## 14. Rollback acceptance (RB)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| RB-01 | Previous signed installer remains available | Check release artifacts | MUST | Download URL |
| RB-02 | Rollback with `/ALLOWDOWNGRADE=1` restores previous version | Install v2, rollback to v1 | MUST | Version check |
| RB-03 | `generated/` and `logs/` preserved during rollback | Compare before/after | MUST | Dir listing |
| RB-04 | Post-rollback healthcheck passes | Run healthcheck | MUST | All green |
| RB-05 | Post-rollback index rebuild succeeds if needed | Run `-Force` reindex | MUST | Stats pass |
| RB-06 | Onboarding state detects version change and re-validates | Check state transitions | SHOULD | JSON content |

---

## 15. Uninstall acceptance (UN)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| UN-01 | Silent uninstall completes without error | `unins000.exe /VERYSILENT` | MUST | Exit code 0 |
| UN-02 | Application files removed | Check `%LOCALAPPDATA%\1c-ai-workbench` | MUST | Dir empty/gone |
| UN-03 | Start Menu shortcut removed | Check Start Menu | MUST | Shortcut gone |
| UN-04 | Registry entries removed | Check `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\` | MUST | Key gone |
| UN-05 | `.venv` and Python cache removed | Check for `.venv` dir | MUST | Dir gone |
| UN-06 | `generated/` preserved | Check dir exists with contents | MUST | Dir listing |
| UN-07 | `logs/` preserved | Check dir exists with contents | MUST | Dir listing |
| UN-08 | `.env` files preserved | Check `.env` exists | MUST | File exists |
| UN-09 | VS Code not affected | `code --version` still works | MUST | Console |
| UN-10 | Continue extension not affected | `code --list-extensions` still lists Continue | MUST | Console |
| UN-11 | Ollama not affected | `ollama --version` still works | MUST | Console |
| UN-12 | No orphaned processes after uninstall | Check Task Manager | SHOULD | Process list |

---

## 16. State machine acceptance (SM)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| SM-01 | State file created on first launch | Run `START_HERE.ps1`, check file | MUST | File exists |
| SM-02 | State advances only on passing validation | Fail a check, verify state unchanged | MUST | State file |
| SM-03 | State persists across PowerShell sessions | Close PS, reopen, rerun; state resumes | MUST | State file |
| SM-04 | State survives installer upgrade | Upgrade, check state file | MUST | State file |
| SM-05 | Invalid state transition rejected | Attempt to skip from `FRESH` to `MCP_OK` | MUST | Error / no-op |
| SM-06 | `CHANGE_APPLIED` is the only file-modifying state | Review state machine logic | MUST | Code review |
| SM-07 | State file is valid JSON per schema | Validate against `onboarding-state.schema.json` | MUST | Validator output |
| SM-08 | Transitions array records every state change | Inspect transitions after full run | MUST | JSON content |
| SM-09 | State file never contains secrets | Grep for key patterns | MUST | Empty grep |
| SM-10 | Resume from interruption works | Kill PS mid-onboarding, rerun | SHOULD | State resumes |

---

## 17. Error catalog acceptance (EC)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| EC-01 | Every error code in Section 9 of the spec exists in `error-catalog.json` | Cross-reference | MUST | Catalog file |
| EC-02 | Every error has RU and EN messages | Inspect catalog | MUST | Catalog file |
| EC-03 | Every error has a recovery action | Inspect catalog | MUST | Catalog file |
| EC-04 | Error codes are stable (no renumbering across versions) | Version the catalog | MUST | Schema version |
| EC-05 | Catalog is valid JSON per schema | Validate | MUST | Validator output |
| EC-06 | Every state machine failure path maps to an error code | Trace all fail branches | MUST | Coverage matrix |
| EC-07 | Error messages do not contain secrets or file contents | Review all messages | MUST | Catalog review |
| EC-08 | Error messages include "learn more" doc reference | Inspect catalog | SHOULD | Catalog file |

---

## 18. Cross-cutting acceptance (XC)

| ID | Criterion | Verification | Tier | Evidence |
|----|-----------|--------------|------|----------|
| XC-01 | Full onboarding completes in <30 minutes on clean VM (excluding AI provider signup) | Time the run | SHOULD | Timing |
| XC-02 | All PowerShell scripts pass PSScriptAnalyzer | `Invoke-ScriptAnalyzer` | MUST | Zero errors |
| XC-03 | All Python scripts pass `ruff` and `mypy` | Run linters | MUST | Zero errors |
| XC-04 | No new files committed to `configs/continue/` | `git diff --name-only` | MUST | Empty diff |
| XC-05 | No changes to `scripts/28_*.ps1`, `scripts/29_*.py`, `scripts/30_*.py` | `git diff --name-only` | MUST | Empty diff |
| XC-06 | No changes to `tests/test_continue_profiles.py` | `git diff --name-only` | MUST | Empty diff |
| XC-07 | No changes to `.github/workflows/` | `git diff --name-only` | MUST | Empty diff |
| XC-08 | No real API keys in any committed file | `gitleaks detect` | MUST | Exit code 0 |
| XC-09 | Conventional commit format used | Inspect commit message | MUST | Commit log |
| XC-10 | PR is Draft and base is `qwen/thin-client-ai-hybrid-v2` | Inspect PR | MUST | PR metadata |

---

## 19. MUST / SHOULD / LATER summary

### MUST count by section

| Section | MUST criteria |
|---------|--------------|
| Clean-Windows (CW) | 15 |
| Environment (EV) | 7 |
| IDE detection (ID) | 6 |
| AI mode (AM) | 7 |
| Key storage (KS) | 11 |
| Source/index (SI) | 10 |
| MCP verification (MV) | 11 |
| First answer (FA) | 8 |
| BSL change (BC) | 10 |
| Live 1C boundary (LB) | 8 |
| Privacy (PR) | 9 |
| Update (UP) | 10 |
| Rollback (RB) | 5 |
| Uninstall (UN) | 11 |
| State machine (SM) | 9 |
| Error catalog (EC) | 7 |
| Cross-cutting (XC) | 9 |
| **Total MUST** | **153** |

### SHOULD count: 14

### LATER items (from spec Section 17.3): 10

---

## 20. Verification environments

| Environment | OS | Purpose |
|-------------|-----|---------|
| Clean VM 1 | Windows 10 21H2 x64, no dev tools | CW, EV, ID, UN |
| Clean VM 2 | Windows 11 22H2 x64, no dev tools | CW, EV, ID, UN |
| Dev host | Windows 10/11 with VS Code, Continue, Ollama | AM, KS, SI, MV, FA, BC, SM |
| Air-gapped host | No network adapter | Local mode (AM-04, PR-09 offline) |

---

## 21. Acceptance sign-off

| Role | Signs for | Date | Status |
|------|-----------|------|--------|
| Implementer | All MUST criteria pass | — | — |
| Reviewer (Codex) | Architecture and integration review | — | — |
| Maintainer | Release approval | — | — |

No production release is approved while any MUST criterion is `FAIL` or
`NOT RUN` without a documented `WAIVED` justification accepted by the
maintainer.
