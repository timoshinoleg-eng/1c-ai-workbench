# Production Release Checklist

## Repository and CI

- [ ] Release commit is reviewed and the pull request head is fully green.
- [ ] CodeQL, Gitleaks, Python, Markdown, REUSE, pre-commit, Rust, PowerShell,
  full integration, and Windows installer jobs pass on the same head SHA.
- [ ] The merged `main` head is frozen before `build-candidate.yml` starts.
- [ ] Hardening work continues on a separate branch and does not change the
  candidate commit.

## Installer payload

- [ ] `requirements-production.lock` was regenerated intentionally and reviewed.
- [ ] Offline wheelhouse metadata reports CPython 3.11 / Windows x64.
- [ ] The wheelhouse contains `THIRD_PARTY_PYTHON.json` and
  `THIRD_PARTY_NOTICES.txt`; its build rejected unresolved or GPL-family licenses.
- [ ] If distributed commercially, Inno Setup terms were reviewed and the required
  commercial license was obtained.
- [ ] Every wheel and both release executables have SHA-256 manifests.
- [ ] `scripts/setup.ps1` pins the published release tag and SHA-256 for the
  exact `code-index 0.45.0` asset; an absent or stale pin fails closed.
- [ ] The installed payload reports exactly `code-index 0.45.0` before offline
  setup, upgrade, downgrade, and uninstall acceptance continue.
- [ ] Offline setup, upgrade preservation, and uninstall acceptance pass.
- [ ] Default downgrade rejection passes; any `/ALLOWDOWNGRADE=1` rollback is
  separately approved and recorded.
- [ ] `generated` and `logs` preservation is communicated to the operator.

## Mandatory external signing gate

- [ ] The protected `release-candidate` environment contains a valid production
  Authenticode certificate and private key.
- [ ] The installer has a valid SHA-256 Authenticode signature and RFC 3161
  timestamp.
- [ ] The signer identity and certificate chain match the publishing entity.
- [ ] `build-candidate.yml` completed for the exact frozen `main` commit.
- [ ] Its exact downloaded artifact is tested on clean Windows 10 and Windows 11
  x64 hosts without developer tools or a prior workbench installation.
- [ ] SmartScreen behavior is recorded; reputation warnings are not represented
  as a code defect, but they must be understood before broad distribution.
- [ ] The durable verification record identifies the candidate run, commit,
  version, hashes, install/smoke results, and uninstall result.

## Publication

- [ ] The protected `production-release` environment approval references the
  clean-Windows verification record.
- [ ] `publish-verified.yml` accepts the candidate run ID and publishes without
  any build or signing step.
- [ ] The release tag is annotated, points to the candidate commit, and was
  never force-updated.
- [ ] The signed installer, `bsl-indexer.exe`, reports, manifest, and checksums
  are the exact files downloaded from the verified candidate run.
- [ ] The final release tag and `bsl-indexer.exe` checksum are written back to
  `scripts/setup.ps1` on the next development commit, without moving the tag.
- [ ] Release notes describe supported Python/Windows versions, offline behavior,
  upgrade behavior, uninstall preservation, and known limitations.
- [ ] Rollback installer and previous signed release remain available.
