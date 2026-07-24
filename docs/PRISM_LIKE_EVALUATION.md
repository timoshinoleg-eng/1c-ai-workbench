# PRISM-like provider-free evaluation

The workbench adapts PRISM's reproducibility principle without copying its
benchmark results or adding a provider dependency. The local suite evaluates
four deterministic contracts over a committed 1C fixture:

- exact BSL symbol navigation;
- evidence found inside a procedure body;
- caller-to-callee graph preservation;
- `ConfigDumpInfo.xml` manifest navigation.

Every result must include a repository-relative source citation with a valid
line range containing the asserted evidence. The runner creates a temporary
copy, builds a fresh index, reads no provider credentials, and makes no network
requests.

```powershell
python .\scripts\26_run_prism_eval.py `
  --json-report .\dist\prism-1c-eval.json `
  --markdown-report .\dist\prism-1c-eval.md
```

Acceptance is all-or-nothing: `4/4` is PASS; any missing symbol, edge, manifest
row, source file, line range, or evidence token fails the process. The optional
provider profile is disabled, denies network access, requires explicit opt-in,
and caps a future approved experiment at USD 0.20.
