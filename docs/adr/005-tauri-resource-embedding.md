## ADR: 005 — Tauri Resource Embedding for Cockpit Self-Contained Install

**Статус:** Accepted
**Implementation:** `tools/cockpit-app/src-tauri/src/embedded.rs`
**Staging script:** `tools/cockpit-app/scripts/prepare-embedded.ps1`

**Контекст:**
Cockpit (`tools/cockpit-app/`) сейчас поставляется как один `.exe` (≈ 20,9 МБ),
но на первом запуске ожидает рядом полноценный workbench: `bsl-indexer.exe`,
Python-MCP серверы (`skills-bridge`, `prompt-gallery`, `help-index-mcp`),
`opencode.jsonc` и вспомогательные скрипты. Баг-репорт
`docs/bug-reports/2026-06-24-cockpit-config-defaults.md` показывает, что
отсутствие этих артефактов в инсталляторе ломает свежую установку: все MCP
серверы падают с `is not running`, а пользователь не получает диагностики.

Цель ADR — зафиксировать, какие именно ресурсы встраивать в Tauri-бандл,
как их разворачивать на машине пользователя и какие риски/ограничения это
влечёт.

**Рассмотренные варианты:**
1. Вариант A — не встраивать ресурсы, а чинить `.iss` инсталлятор, чтобы он
   копировал workbench рядом с `.exe`.
2. Вариант B — встроить минимальный набор ресурсов внутрь `.exe` через
   Tauri `bundle.resources`, а при первом запуске распаковать их в
   `%APPDATA%\1c-ai-workbench\`.
3. Вариант C — встроить весь workbench целиком (включая скрипты, `docs/`,
   `generated/`, тестовые данные).

**Решение:** Вариант B — встроить минимальный self-contained набор ресурсов
и распаковывать их через `tauri::resource_dir()` → `%APPDATA%\1c-ai-workbench\`
с sentinel-файлом `.embedded-by-cockpit-v1`.

**Обоснование:**
Вариант A не решает проблему offline-сценария и сохраняет хрупкую связь
между установщиком и файловой структурой workbench. Вариант C неоправданно
раздувает `.exe`, включает customer-данные и нарушает границы read-only
поставки. Вариант B даёт "один файл для установки", сохраняет v1 scope и
оставляет дверь открытой для Phase B / v2 cross-platform.

**Что встраивать (минимальный набор для offline v1):**

| Ресурс | Назначение | Ориентировочный размер |
|--------|-----------|------------------------|
| `tools/code-index-mcp/target/release/bsl-indexer.exe` | Rust MCP сервер для индексации BSL/XML | ≈ 25 МБ |
| `tools/skills-bridge/**` | Python FastMCP сервер `1c-skills` | ≈ 5 МБ |
| `tools/prompt-gallery/**` | Python FastMCP сервер `1c-prompt-gallery` | ≈ 5 МБ |
| `tools/help-index-mcp/**` | Python FastMCP сервер `1c-help-index` | ≈ 5 МБ |
| `opencode.jsonc` (минимальная версия) | Canonical MCP config без live-1c-bridge | < 0,1 МБ |

Итого: ≈ +40–45 МБ к текущему `.exe`.

**Что НЕ встраивать:**
- Customer-данные: `dump/`, `generated/index/source-mirror/`, `.code-index/`.
- Сгенерированные артефакты: `generated/code-index-home/`,
  `generated/help-index/`, `generated/reports/`.
- Логи: `*.log`, `.coverage-html/`, `.pytest_cache/`, `.ruff_cache/`.
- Секреты и локальные настройки: `.env`, `config.json` пользователя,
  `%APPDATA%\1c-ai-cockpit\config.json`.
- Юридические и коммерческие документы: `docs/legal/**`.
- Phase B / live компоненты: `tools/ibcmd-bridge/` (опциональный Phase B,
  требует отдельного `ibcmd.exe`) и `tools/live-1c-bridge/` (.NET/COM bridge,
  вне scope v1).

**Layout ресурсов и распаковка:**
- В `.exe` ресурсы попадают через `bundle.resources` в `tauri.conf.json`
  (или через `externalBin` для `bsl-indexer.exe`, если требуется отдельный
  бинарник с правами).
- Runtime resolution: `tauri::resource_dir()` → `<install>\resources\` (dev) /
  `<install>\resources\` или внутри `.exe` (prod).
- First-run extractor (Tauri setup hook / `run()`):
  1. Проверить `%APPDATA%\1c-ai-workbench\.embedded-by-cockpit-v1`.
  2. Если sentinel отсутствует — скопировать дерево ресурсов в
     `%APPDATA%\1c-ai-workbench\embedded\`.
  3. Записать sentinel с версией сборки и timestamp.
  4. Использовать `%APPDATA%\1c-ai-workbench\embedded\` как `workbenchPath`
     по умолчанию в `config.rs`.
- Обновление sentinel должно происходить атомарно: сначала распаковка во
  временную директорию, затем rename, чтобы избежать частичного состояния
  при аварийном завершении.

**Size budget:**
- Текущий `cockpit-app.exe` ≈ 20,9 МБ (по данным баг-репорта).
- Добавка: `bsl-indexer.exe` 25 МБ + три Python-пакета ≈ 15 МБ +
  зависимости/накладные расходы ≈ 5 МБ.
- Итоговый `.exe` ≈ 65 МБ.



**Влияние на code signing:**
- Встраивание ресурсов меняет байтовое содержимое `.exe`, следовательно,
  меняется хеш и требуется повторная подпись.
- SmartScreen / Defender SmartScreen reputation привязана к хешу подписанного
  бинарника; изменение ресурсов сбрасывает накопленную репутацию.
- Оценка регрессии:
  - Повторная подпись EV/OV сертификатом: 1–2 дня (включая CI pipeline).
  - Повторная валидация SmartScreen: 1–4 недели до восстановления зелёной
    репутации; в первые дни возможен жёлтый экран "Unknown publisher" даже
    при валидной подписи.
  - Если используется Microsoft Defender for Business / Application Control:
    потребуется обновить правила путём/хешей.
- Рекомендация: автоматизировать подпись в CI и вести журнал хешей релизов.

**Путь обновления bsl-indexer:**
1. Вариант (a) — полная пересборка `.exe` с новой версией `bsl-indexer.exe`.
   Рекомендуется для v1: просто, предсказуемо, не требует серверной
   инфраструктуры для доставки обновлений.
2. Вариант (b) — extract-only mode, при котором `.exe` не содержит
   `bsl-indexer.exe`, а скачивает его при первом запуске из отдельного
   артефакта. Более гибкий, но требует канала доставки, проверки хешей и
   fallback для offline.

Для v1 выбираем (a). Вариант (b) оставляем для v2, если появится
self-update channel.

**Cross-platform:**
- v1 — только Windows 10/11, что зафиксировано в
  операционном runbook.
- v2+:
  - macOS: `.app` бандл с ресурсами внутри `Contents/Resources/`.
  - Linux: AppImage со встроенными ресурсами в `usr/share/1c-ai-workbench/`.
- В v1 не реализуем cross-platform extraction; код распаковки должен быть
  спроектирован так, чтобы путь к embedded-ресурсам задавался через
  `tauri::resource_dir()` без Windows-specific хардкода.

**Risk register:**

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Антивирусные false positives: встраивание бинарника (`bsl-indexer.exe`) внутрь `.exe` может выглядеть для эвристики как упаковка/внедрение полезной нагрузки. | средняя | высокое | Подписывать `.exe` EV сертификатом; отправлять каждый релиз на вайтлистинг в Microsoft, VirusTotal; избегать UPX/самораспаковки; вести журнал ложных срабатываний. |
| Раздувание размера дистрибутива: +45 МБ увеличивает время скачивания и занимаемое место. | высокая | среднее | Зафиксировать бюджет < 100 МБ; в Phase B рассмотреть сжатие Python-зависимостей (zipapp, standalone Python) или вариант (b) обновления. |
| Time-to-first-launch: распаковка 40+ МБ на медленном диске может занять десятки секунд, пользователь видит "зависший" экран. | средняя | высокое | Показывать progress bar в onboarding; распаковывать lazy по мере необходимости (сначала `bsl-indexer`, затем Python MCP); кэшировать между запусками. |
| Silent failure при нехватке диска: распаковка в `%APPDATA%` может не хватить места, а пользователь получит `is not running`. | средняя | высокое | Перед распаковкой проверять свободное место (хотя бы 2× размер ресурсов); при нехватке показывать явную ошибку с путём и требуемым объёмом; не перезаписывать sentinel при неполной распаковке. |
| Несовпадение версий: sentinel от старой сборки может маскировать устаревшие ресурсы после обновления `.exe`. | низкая | высокое | Включать версию сборки в имя/содержимое sentinel; при несовпадении версий перераспаковывать полностью. |

**Последствия:**
- `tauri.conf.json` получит ненулевой `bundle.resources`.
- Появится setup-hook / модуль распаковки в `tools/cockpit-app/src-tauri/src/`.
- `config.rs` будет использовать `%APPDATA%\1c-ai-workbench\embedded\` как
  fallback/default `workbenchPath` вместо хардкода `C:\1c-ai-workbench`.
- Упрощается onboarding: свежая установка без отдельного workbench install.
- Увеличивается время сборки и размер артефакта; требуется перенастройка
  code signing и мониторинг SmartScreen reputation.

**Compliance с BORROWING_MAP:**
- Есть ли заимствование? нет, используются собственные компоненты проекта.
- Если да — указана ли лицензия? не применимо.
- Нарушает ли границы? нет, встроенные ресурсы остаются read-only и не
  включают customer data.
