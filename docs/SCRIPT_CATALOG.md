# Script Catalog

Этот каталог отделяет команды, необходимые для пилота, от developer-only утилит. Запускайте PowerShell-скрипты из корня workbench и сначала проходите [ENTERPRISE_FIRST_RUN.md](ENTERPRISE_FIRST_RUN.md).

## Pilot-critical path

| Script | Назначение | Когда запускать |
|---|---|---|
| `01_check_env.ps1` | Проверяет базовые prerequisites | До setup и при диагностике |
| `scripts/setup.ps1` | Создаёт virtual environment и ставит зависимости | Один раз на environment |
| `04_index_1c_dump.ps1` | Создаёт mirror и индексирует XML dump | После размещения согласованного dump |
| `06_healthcheck.ps1` | Проверяет готовность компонентов | После setup/index и перед demo |
| `16_check_skills_bridge.ps1` | Smoke check skills bridge | После setup |
| `17_check_ibcmd_bridge.ps1` | Smoke check ibcmd bridge и default write gate | После setup |
| `18_check_prompt_gallery.ps1` | Smoke check prompt gallery | После setup |
| `22_run_e2e_smoke.ps1` | Сквозной smoke workflow | Перед handoff/acceptance |
| `28_collect_release_evidence.ps1` | Собирает hash, version и Authenticode evidence | До пилота и для каждого artifact |
| `07_clean_generated.ps1` | Очищает только generated output | Для recovery; не удаляет source dump |

## Release и distribution

| Script | Назначение |
|---|---|
| `03_build_bsl_indexer.ps1` | Developer build Rust binary из source |
| `19_build_windows_installer.ps1` | Собирает Windows installer |
| `23_prepare_offline_wheelhouse.ps1` | Готовит offline wheelhouse для поддерживаемого Python profile |
| `24_test_windows_installer.ps1` | Проверяет installer на Windows |
| `25_validate_code_index_045.py` | Проверяет pinned code-index contract |

## Quality и analysis

| Script | Назначение |
|---|---|
| `10_risk_scan.ps1` | Локальный security/risk scan |
| `13_check_bsl_quality_pack.ps1` | Проверяет BSL quality pack |
| `14_check_testing_pack.ps1` | Проверяет testing pack |
| `15_check_review_pack.ps1` | Проверяет review pack |
| `21_export_mcp_context.ps1` | Экспортирует MCP context для диагностики |
| `26_run_prism_eval.py` | Запускает PRISM-like evaluation |
| `27_validate_optional_adapters.py` | Проверяет optional adapters |

## Developer-only and legacy utilities

| Script | Статус |
|---|---|
| `08_launch_1c_training.ps1` | Developer/demo utility; не требуется для pilot path |
| `09_dump_ut_demo_config.ps1` | Developer fixture utility |
| `10_index_ut_demo_dump.ps1` | Developer fixture utility |
| `09_generate_repo_map.ps1` | Developer documentation utility |
| `11_explain_module.ps1` | Ad-hoc helper |
| `11_open_demo_showcase.ps1` | Demo launcher |

> В каталоге исторически существуют одинаковые числовые префиксы `09_`, `10_` и `11_`. Они не означают порядок выполнения и не должны вызываться по glob/числовому диапазону. В следующем breaking-cleanup релизе их следует переименовать в смысловые имена или перенести в `scripts/dev/` с compatibility wrappers.
