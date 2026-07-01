# Security

## Threat model

1C AI Workbench is designed to run locally on a Windows workstation.
The default configuration is read-only and does not require external
network access to operate.

Primary risks:

- **Local secrets in prompts.** API keys, passwords, or tokens may be
  passed to an LLM client. The workbench itself does not store them,
  but the operator's client configuration might.
- **Exfiltration through generated artifacts.** Indexes, logs, and
  reports contain file paths and code snippets. Do not publish them
  to public URLs.
- **Live write paths.** `ibcmd` bridge write operations are disabled
  by default and require explicit `IBCMD_ALLOW_WRITE=1` plus a
  confirmation flag.
- **Supply chain.** The Rust `bsl-indexer` and Python bridges use
  vendored dependencies. Apply vendor patches with
  `tools/apply-vendor-patches.ps1` after every subtree update.

## Hard defaults

- Read-only mirror of the 1C XML dump before indexing.
- No automatic upload or telemetry.
- No bundled proprietary 1C binaries.
- API keys are owned and configured by the operator.

## Reporting

Open a private security issue or email the maintainer if you discover
a vulnerability that should not be discussed in public before a fix
is released.

## See also

- [docs/SECURITY_OVERVIEW.md](docs/SECURITY_OVERVIEW.md)
