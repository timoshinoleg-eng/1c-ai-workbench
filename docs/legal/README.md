# Legal artifacts

This directory holds artifacts produced by automated license and secret
scans, plus the borrowing map and related legal documentation.

## Files

- `BORROWING_MAP.md` — complete account of third-party code, ideas, and
  patterns referenced or adapted, with license boundaries.
- `scans/gitleaks-<date>.txt` — gitleaks secret-scan results for the
  repository history.
- `scans/scancode-<date>.json` — scancode-toolkit full license scan results.
- `scans/reuse-<date>.txt` — REUSE-compliance check output.
- `scans/pip-licenses-<date>.md` — Python dependency license inventory.

## Re-running scans

```powershell
# gitleaks (secrets in git history)
gitleaks detect --no-git -v > docs/legal/scans/gitleaks-$(Get-Date -Format yyyy-MM-dd).txt

# scancode-toolkit (full license audit)
scancode -clipeu --json docs/legal/scans/scancode-$(Get-Date -Format yyyy-MM-dd).json .

# REUSE compliance (FSF SPDX validator)
reuse lint > docs/legal/scans/reuse-$(Get-Date -Format yyyy-MM-dd).txt

# Python dependency licenses
pip-licenses --format=markdown --output-file=docs/legal/scans/pip-licenses-$(Get-Date -Format yyyy-MM-dd).md
```

The release checklist in `RELEASE_CHECKLIST.md` requires that all of these
scans pass before tagging a release.
