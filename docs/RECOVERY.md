# Recovery: when healthcheck goes red

Краткая шпаргалка для случая, когда `scripts/06_healthcheck.ps1` показывает
`Status: Blocked` или любой из шести чеков в `generated/reports/readiness-report.html`
горит красным.

## 0. Что красное?

`06_healthcheck.ps1` проверяет ровно шесть вещей:

| # | Чек | Что значит Ready |
|---|---|---|
| 1 | `binary exists` | `tools\code-index-mcp\target\release\bsl-indexer.exe` собран |
| 2 | `index exists` | `generated\index\source-mirror\.code-index\index.db` создан |
| 3 | `logs writable` | `logs\` доступен на запись |
| 4 | `stats command` | `bsl-indexer stats` отрабатывает на индексе без ошибок |
| 5 | `query smoke` | `bsl-indexer search-text` возвращает ≥1 hit на тестовом запросе |
| 6 | `mcp help` | `bsl-indexer --help` отрабатывает (MCP transport работоспособен) |

Файл отчёта: `generated\reports\readiness-report.md` (markdown) и
`generated\reports\readiness-report.html` (визуально).

## 1. binary exists — FAIL

**Симптом:** `missing ...\target\release\bsl-indexer.exe`.

**Причина:** Rust-бинарь не собран. Это блокер — без него локальный поиск и MCP
code-index не стартуют.

**Фикс:**

```powershell
cd C:\1c-ai-workbench
.\scripts\03_build_bsl_indexer.ps1 -WorkbenchRoot .
```

Ожидаемое время: 8-12 минут на первой сборке (~280 crates). Последующие
сборки — секунды (incremental).

Если cargo не находится — установить [rustup](https://rustup.rs/) и перезапустить
PowerShell.

## 2. index exists — FAIL

**Симптом:** `missing ...\generated\index\source-mirror\.code-index\index.db`.

**Причина:** dump не проиндексирован (или был удалён).

**Фикс:**

```powershell
# Положить 1С XML/BSL dump в C:\1c-ai-client\dump
mkdir C:\1c-ai-client\dump -ErrorAction SilentlyContinue
# (скопировать файлы выгрузки)

cd C:\1c-ai-workbench
.\scripts\04_index_1c_dump.ps1 -WorkbenchRoot . -DumpRoot C:\1c-ai-client\dump -Force
```

Проверить, что дамп не пустой: `Get-ChildItem C:\1c-ai-client\dump -Recurse -File | Measure-Object`
должен показать `Count > 0` и наличие `Configuration.xml` где-то в дереве.

## 3. logs writable — FAIL

**Причина:** антивирус / EDR / некорректные права на папку.

**Фикс:** убедиться, что у пользователя есть `Modify` на `C:\1c-ai-workbench\logs\`.
Не запускать workbench из `C:\Program Files\` (прав не хватит даже с UAC).

## 4. stats command — FAIL

**Симптом:** `unable to open database file` или другая SQLite-ошибка.

**Причина:** обычно бинарь (1) или индекс (2) не консистентны — лечить
первые два чека. Если они зелёные, а stats падает, проверить `logs\stats.json.err`
для root cause.

## 5. query smoke — FAIL

**Симптом:** `No smoke search query returned results`.

**Причина:** индекс существует, но пустой или без объектов, по которым
идёт тестовый запрос. Типично для:

- минимального синтетического dump (нет BSL-модулей);
- повреждённой индексации (бинарь обновился, индекс от старого);
- пустой выгрузки 1С.

**Фикс:**

1. Положить реальный dump и переиндексировать (`-Force` в шаге 2).
2. Если dump непустой и ошибка повторяется — открыть
   `logs\smoke-search-text.txt` (последний запрос) и
   `logs\smoke-search-text.err` (stderr) и приложить к тикету.

## 6. mcp help — FAIL

**Симптом:** `bsl-indexer --help` падает или возвращает non-zero.

**Причина:** бинарь из шага 1 повреждён (частичная сборка, антивирус
удалил `.exe` между сборкой и healthcheck, или несовместимая ОС).

**Фикс:** пересобрать (`scripts/03_build_bsl_indexer.ps1`). Если вторая
сборка тоже падает — собрать вручную для отладки:

```powershell
cd C:\1c-ai-workbench\tools\code-index-mcp
cargo build --release -p bsl-indexer
```

и приложить stderr.

## 7. Если после всех шагов красное

Собрать evidence-пакет для тикета:

```powershell
$dst = "C:\temp\1c-ai-evidence-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item logs\06_healthcheck.log $dst -ErrorAction SilentlyContinue
Copy-Item generated\reports\readiness-report.* $dst
Copy-Item logs\stats.json.err $dst -ErrorAction SilentlyContinue
Copy-Item logs\smoke-search-text.* $dst -ErrorAction SilentlyContinue
git -C C:\1c-ai-workbench rev-parse HEAD | Out-File "$dst\commit.txt"
git -C C:\1c-ai-workbench status --short | Out-File "$dst\git-status.txt"
Write-Host "Evidence in $dst"
```

ZIP и приложить к issue.

## 8. Если ничего не помогло

Открыть issue с тегами `area:healthcheck`, `blocker` и приложить evidence-пакет
из шага 7. Включить:

- вывод `git rev-parse HEAD` (зафиксировать точный коммит);
- версию Windows (`winver`);
- вывод `cargo --version` и `rustc --version`;
- содержимое `logs/06_healthcheck.log`.

## 9. Что НЕ делать

- **Не удалять `generated/index/` без переиндексации.** Это единственный
  источник данных для `bsl-indexer`. Удаление = cold start.
- **Не править `tools/cc-1c-skills/.claude/skills/*/scripts/*.py`** без
  понимания что это upstream — каждое изменение нужно оформлять как
  PR в `Nikolay-Shirokov/cc-1c-skills` (см. `tools/SUBTREE.md`).
- **Не включать `live-1c-bridge` или `ibcmd-bridge` в production-v1 baseline.**
  Они по умолчанию отключены в `opencode.jsonc` (см. `generated/reports/corporate-mode-report.md`).
  Включение = выход за read-only baseline, требует отдельного
  решения по security review.
