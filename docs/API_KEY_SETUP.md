# API-ключи для пилота

## Короткое правило

Не передавайте партнёру сборку с постоянным API-ключом исполнителя. Для реальной базы используется ключ клиента или временный тестовый ключ с лимитом и отзывом после проверки.

## Вариант 1 — без внешнего клиента

Для первичной проверки можно использовать локальный поиск без подключения внешнего клиента:

```powershell
.\tools\code-index-mcp\target\release\bsl-indexer.exe search-text "Контрагенты" --path "C:\1c-ai-workbench\generated\index\source-mirror" --limit 5
```

Плюсы: данные не уходят во внешние сервисы, проще согласовать безопасность. Минус: нет полноценного диалогового интерфейса.

## Вариант 2 — ключ клиента

1. Клиент создаёт отдельный ключ у выбранного провайдера внешнего клиента.
2. Для ключа задаётся лимит расходов на пилот.
3. Ключ вводится только на машине клиента в конфиг внешнего клиента или локальный `.env`.
4. После пилота ключ отзывается или удаляется.

Не коммитьте и не отправляйте ключи в чатах, скриншотах, архивах и логах.

## Вариант 3 — временный тестовый ключ

Если клиент пока не готов создавать ключ:

1. Создайте отдельный временный ключ только под этот пилот.
2. Поставьте лимит расходов, например `$5–10`.
3. Укажите срок действия `1–3 дня`.
4. Используйте только демо-выгрузку или заранее согласованную копию.
5. После проверки отзовите ключ и удалите его из конфигов.

## Куда вводить ключ

Точное место зависит от внешнего клиента:

- `External MCP client`: настройте клиент вручную по его документации; ключ вводится только на машине клиента.
- `opencode`: настройка провайдера в opencode; MCP-подключение описано в `docs\OPENCODE_SETUP_RU.md`.
- `Cursor` / `VS Code`: настройки выбранного расширения или провайдера.
- `.env`: только локальный файл, не попадающий в архив или Git. В репозитории оставляйте только пример `configs\external-client.env.example`.

## Continue и ключи (Thin Client AI)

С v1 профили provider-neutral: HostedAgent принимает любого OpenAI-compatible
провайдера (своего ключа — BYOK, своей модели — BYOM). Groq-профиль Online Hybrid
сохранён как legacy preset.

### Provider-neutral (HostedAgent) — bring your own key / model

Ключ моделируется только **именем** Continue-секрета. Генератор никогда не принимает,
не печатает и не встраивает значение ключа.

```powershell
# Kimi Code: официальный coding endpoint, модель и обязательная temperature=1
.\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent -Preset kimi
#   -> ссылка ${{ secrets.KIMI_API_KEY }}, endpoint https://api.kimi.com/coding/v1

# Preset с проверенным endpoint и именем секрета (Z.AI)
.\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent -Preset zai
#   -> ссылка ${{ secrets.ZAI_API_KEY }}, endpoint https://api.z.ai/api/paas/v4

# Свой провайдер: своё имя секрета, endpoint и модель
.\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent `
    -ApiBase https://openrouter.ai/api/v1 -ModelId anthropic/claude-3.5-sonnet `
    -SecretName OPENROUTER_API_KEY
```

- Для `kimi` нужен ключ из Kimi Code Console. Ключи Kimi Open Platform
  (`https://api.moonshot.cn/v1`) с Kimi Code endpoint не взаимозаменяемы.
- Не передавайте значение ключа как `-SecretName`/`-ModelId`/`-ApiBase` — генератор
  отклонит всё, что похоже на реальный ключ (префиксы `gsk_`/`sk-`/... или длинная
  base64-подобная строка).
- `-ApiBase` обязан быть HTTPS без userinfo/query/fragment.
- Для IDE Continue ищет именованный секрет по порядку в workspace `.env`, workspace
  `.continue/.env`, затем `%USERPROFILE%/.continue/.env`. Process environment
  доступен только Continue CLI и не удовлетворяет IDE-oriented `-RequireRuntimeReady`.
- Не вставляйте реальное значение ключа в `configs/continue/*.yaml` или в
  сгенерированный профиль и не коммитьте `.env`.

### Legacy: Online Hybrid (Groq)

Профиль Online Hybrid использует Groq для chat/edit/apply. Ключ настраивается
поддерживаемым механизмом секретов/переменных окружения Continue; в YAML-профиле
хранится только ссылка `${{ secrets.GROQ_API_KEY }}`.

- Для IDE Continue ищет `GROQ_API_KEY` по порядку в workspace `.env`, workspace
  `.continue/.env`, затем `%USERPROFILE%/.continue/.env`. Process environment
  доступен только Continue CLI и сам по себе не удовлетворяет IDE-oriented
  `-RequireRuntimeReady`.
- Генератор `scripts/28_prepare_continue_profile.ps1` не принимает ключ как
  параметр, не печатает и не встраивает его. `-RequireRuntimeReady` читает только
  dotenv-строки, чтобы определить наличие непустой записи именованного секрета, и не
  передаёт значение probe-процессам.

### LocalAgent и Offline Lite

LocalAgent и Offline Lite ключей не используют вовсе: только loopback HTTP, без
облачных URL и секретов. Для OpenAI-compatible LocalAgent обязателен путь `/v1`;
Ollama autocomplete использует native root. Подробнее —
[CONTINUE_THIN_CLIENT.md](CONTINUE_THIN_CLIENT.md).

## Перед отправкой архива

Проверьте:

```powershell
Select-String -Path .\**\* -Pattern "sk-|api_key|token|password|secret" -SimpleMatch -ErrorAction SilentlyContinue
```

Если найден реальный секрет — удалите его, пересоздайте архив и отзовите ключ.
