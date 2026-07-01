# E2E Smoke Pipeline

Единый end-to-end smoke pipeline для regression-проверки workbench после любых правок.

## Назначение

Pipeline связывает все ключевые smoke-проверки в один прогон с итоговым verdict. Закрывает regression risk: одно нажатие — и видно, не сломалось ли что-то.

## Запуск

```powershell
cd C:\1c-ai-workbench
.\scripts\22_run_e2e_smoke.ps1 -SkipIndex
```

С полной переиндексацией (долго):

```powershell
.\scripts\22_run_e2e_smoke.ps1
```

Для CI (warnings = fail):

```powershell
.\scripts\22_run_e2e_smoke.ps1 -SkipIndex -Strict
```

С открытием report после PASS:

```powershell
.\scripts\22_run_e2e_smoke.ps1 -SkipIndex -OpenReport
```

## Шаги

| # | Name | Script | Что проверяет |
|---|---|---|---|
| 0 | env_precheck | inline | python, bsl-indexer.exe, dump dir |
| 1 | index_1c_dump | 04_index_1c_dump.ps1 | переиндексация выгрузки (-SkipIndex чтобы пропустить) |
| 2 | healthcheck | 06_healthcheck.ps1 | binary, index, logs, stats, query, mcp help (6 checks) |
| 3 | skills_bridge_smoke | 16_check_skills_bridge.ps1 | 16 tools, audit_metadata, cf_info, validate |
| 4 | ibcmd_bridge_smoke | 17_check_ibcmd_bridge.ps1 | 6 tools, dry-run, write-gate, compare |
| 5 | prompt_gallery_smoke | 18_check_prompt_gallery.ps1 | 23 tools, 20 prompts, render, search |
| 6 | corporate_mode_report | 20_check_corporate_mode.ps1 | policy, MCP disabled, gitignore, secret scan |
| 7 | mcp_context_inspector | 21_export_mcp_context.ps1 | 8 servers, 20 prompt tools, 12 integration tools |
| 8 | local_search_smoke | inline | bsl-indexer search-text по 5 queries |

## Verdict

- **PASS** — все шаги PASS (или SKIP для опциональных)
- **FAIL** — хотя бы один шаг FAIL
- **FAIL_STRICT** — есть warnings и `-Strict`
- **BLOCKED** — env precheck failed (python/binary/dump missing)

## Exit codes

| Code | Значение |
|---|---|
| 0 | PASS |
| 1 | FAIL или FAIL_STRICT |
| 2 | BLOCKED (env precheck) |

## Параметры

| Параметр | Default | Назначение |
|---|---|---|
| `-WorkbenchRoot` | parent of scripts/ | корень workbench |
| `-DumpRoot` | `C:\1c-ai-client\dump` | путь к выгрузке 1С |
| `-SkipIndex` | false | пропустить шаг 1 (переиндексацию) |
| `-OpenReport` | false | открыть MD report после PASS |
| `-Strict` | false | warnings считать failures |

## Artifacts

| Файл | Формат |
|---|---|
| `generated\reports\22_e2e_smoke_report.md` | Markdown |
| `generated\reports\22_e2e_smoke_report.json` | JSON |
| `generated\reports\readiness-report.html` | HTML (step 2) |
| `generated\reports\corporate-mode-report.md` | Markdown (step 6) |
| `generated\reports\mcp-context-report.md` | Markdown (step 7) |
| `logs\22_e2e_smoke.log` | transcript |

## Когда запускать

- После любых правок в `tools/`, `scripts/`, `configs/`, `opencode.jsonc`
- Перед коммитом в main
- Перед сборкой installer (`scripts\19_build_windows_installer.ps1`)
- Перед пилотной поставкой клиенту

## CI integration

```yaml
# пример GitHub Actions
- name: E2E smoke
  run: |
    cd C:\1c-ai-workbench
    .\scripts\22_run_e2e_smoke.ps1 -SkipIndex -Strict
  shell: powershell
```

Exit code 0 = pipeline green, можно мерджить. Non-zero = block.

## Типичное время прогона

| Режим | Время |
|---|---|
| `-SkipIndex` | ~32 s (8 steps, bridges ~30 s) |
| полный (с индексацией) | ~32 s + время индексации (зависит от размера выгрузки) |

На demo-выгрузке (~5 каталогов) — индексация ~10-20 s. На реальной конфигурации (УТ/ERP) — 2-10 минут.
