# Pilot Technical Acceptance Checklist

Заполняйте этот checklist для каждого пилотного environment. Поле `evidence` должно содержать ссылку на локальный report, hash или номер тикета, а не секреты, credentials или исходный dump.

| ID | Проверка | Pass criterion | Evidence | Status |
|---|---|---|---|---|
| R-01 | Source provenance | Release tag и target commit зафиксированы |  |  |
| R-02 | Binary integrity | SHA-256 совпадает с release checksum |  |  |
| R-03 | Binary identity | `bsl-indexer.exe --version` завершился с code 0 |  |  |
| R-04 | Signing | Authenticode status соответствует утверждённой policy |  |  |
| E-01 | Execution policy | Policy проверена; глобальный bypass не использовался |  |  |
| E-02 | Endpoint controls | AV/App Control outcome зафиксирован |  |  |
| E-03 | Network mode | Online proxy либо offline wheelhouse подтверждён |  |  |
| I-01 | Environment | Python, PowerShell, Git и prerequisites прошли check |  |  |
| I-02 | Setup | `setup.ps1` завершился без неразрешённых ошибок |  |  |
| I-03 | Health | Healthcheck завершился Ready/PASS по утверждённому профилю |  |  |
| S-01 | Read-only default | Default tools не изменили source dump и не открыли write path |  |  |
| S-02 | Write gate | Import без `IBCMD_ALLOW_WRITE=1` и explicit confirmation заблокирован |  |  |
| S-03 | Path policy | MCP-клиент не может выбрать произвольный executable или путь вне workspace |  |  |
| S-04 | Secret handling | Logs/MCP responses не содержат credentials и абсолютные пользовательские пути |  |  |
| X-01 | Index | Согласованный XML dump проиндексирован; source mirror и index созданы |  |  |
| X-02 | Search | Минимум три demo-вопроса возвращают проверяемые evidence snippets |  |  |
| X-03 | Manual confirmation | 1С-разработчик подтвердил каждый demo-result вручную |  |  |
| M-01 | MCP client | Клиент подключён по stdio, tools доступны в нужном profile |  |  |
| H-01 | Handoff | Evidence, healthcheck, exceptions и owner переданы |  |  |

## Итоговое решение

| Поле | Значение |
|---|---|
| Pilot environment |  |
| Release tag / commit |  |
| Operator |  |
| Customer technical owner |  |
| Date (UTC) |  |
| Decision | `ACCEPTED` / `ACCEPTED WITH EXCEPTIONS` / `NOT ACCEPTED` |
| Open exceptions |  |

> `ACCEPTED WITH EXCEPTIONS` допустим только при письменном владельце каждого исключения, сроке устранения и отсутствии нарушения read-only guarantee или release-integrity policy.
