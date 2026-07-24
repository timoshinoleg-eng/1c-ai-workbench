# Optional external 1C adapters

July 2026 candidates are recorded in `configs/optional-adapters.json`, but none
is downloaded, bundled, started, or granted credentials by the default setup.
The contract is fail-closed: every adapter is disabled, has no allowed roots,
cannot inherit credentials, and cannot perform writes.

The catalog currently covers MXL semantic merge, a read-only-first OData MCP
candidate, and an external live-base MCP compatibility target. Activation is a
separate disposable-environment pilot, not part of production installation.

```powershell
python .\scripts\27_validate_optional_adapters.py
```

Any future enablement must add an adapter-specific contract test, explicit data
boundary, secret storage procedure, rollback/removal check, and a new security
review. Write-capable OData or live-base operations require separate approval.
