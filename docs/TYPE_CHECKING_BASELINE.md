# Type-checking Baseline

This document records the type-checking status of the controlled-pilot line. It is deliberately an **evidence record**, not a claim that the full Python surface is type-clean.

| Field | Value |
|---|---|
| Public-main base | `4cfb0b277cb37712b84e8790f973da45c35a2c6c` |
| Minimum CI patch ancestor | `1a6aa7c88af3b8cae3f3b7997caa11bc04bf69d1` |
| Tool | mypy 2.3.0 |
| Python environment | Isolated Python 3.12 verification environment |
| Measured date | 2026-08-15 UTC |

## CI semantics

The `Mypy baseline (advisory; existing typing debt)` CI step is intentionally **non-blocking**. It is no longer masked by `|| true`; GitHub will surface a permitted failure through `continue-on-error: true`. The check must not be used as evidence of type cleanliness.

The intended pilot-critical gates remain the fail-closed Rust build/test, Python tests, PowerShell parser/smoke checks, secret scan, license check and installer checks. Type debt is tracked separately so it does not silently disappear from CI output or delay a read-only controlled pilot with unrelated refactoring.

## Baseline results

A repository-wide invocation (`mypy .`) stops at a duplicate top-level module name (`conftest`) before useful debt can be measured. The existing CI target list has the same collision between MCP server modules named `server`. Running each server separately produced the following baseline:

| Entry point | Errors | Notes |
|---|---:|---|
| `tools/skills-bridge/server.py` | 5 | Return `Any`, metadata typing and sort-key typing |
| `tools/prompt-gallery/server.py` | 3 | Sort-key typing and return `Any` |
| `tools/help-index-mcp/server.py` | 10 | `PeekableIterator` generic use, parser return type and undefined symbol |
| **Total** | **18** | Historical typing debt; no pilot-runtime code was changed to suppress it |

## Retirement plan

A future type-hardening series should first make server directories unambiguous Python packages or use a stable module invocation model. It should then fix errors by subsystem, add a small blocking scope only after that scope is clean, and expand the gate only through separately reviewed commits. Do not silence these errors with broad `ignore_errors`, global `disable_error_code`, or another shell-level success mask.

## Reproduction

```text
mypy tools/skills-bridge/server.py
mypy tools/prompt-gallery/server.py
mypy tools/help-index-mcp/server.py
```

Record the exact candidate SHA, mypy version, Python version, command, exit code and full output whenever this baseline is remeasured.
