# Production Release Checklist

## Repository and CI

- [ ] Release commit is reviewed and the pull request head is fully green.
- [ ] CodeQL, Gitleaks, Python, Markdown, REUSE, pre-commit, Rust, PowerShell,
  full integration, and Windows installer jobs pass on the same head SHA.
- [ ] Working tree is clean and the release tag points exactly to that head SHA.

## Installer payload

- [ ] `requirements-production.lock` was regenerated intentionally and reviewed.
- [ ] Offline wheelhouse metadata reports CPython 3.11 / Windows x64.
- [ ] The wheelhouse contains `THIRD_PARTY_PYTHON.json` and
  `THIRD_PARTY_NOTICES.txt`; its build rejected unresolved or GPL-family licenses.
- [ ] If distributed commercially, Inno Setup terms were reviewed and the required
  commercial license was obtained.
- [ ] Every wheel and both release executables have SHA-256 manifests.
- [ ] Offline setup, upgrade preservation, and uninstall acceptance pass.
- [ ] Default downgrade rejection passes; any `/ALLOWDOWNGRADE=1` rollback is
  separately approved and recorded.
- [ ] `generated` and `logs` preservation is communicated to the operator.

## Mandatory external signing gate

- [ ] A valid production Authenticode certificate and private key are available
  through protected GitHub Actions secrets or an approved hardware-backed store.
- [ ] The installer has a valid SHA-256 Authenticode signature and RFC 3161
  timestamp.
- [ ] The signer identity and certificate chain match the publishing entity.
- [ ] The signed installer is tested on a clean supported Windows host.
- [ ] SmartScreen behavior is recorded; reputation warnings are not represented
  as a code defect, but they must be understood before broad distribution.

## Publication

- [ ] The signed installer, `bsl-indexer.exe`, and their checksum files are the
  exact assets produced by the tagged release workflow.
- [ ] Release notes describe supported Python/Windows versions, offline behavior,
  upgrade behavior, uninstall preservation, and known limitations.
- [ ] Rollback installer and previous signed release remain available.
