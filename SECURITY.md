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

## Continue Thin Client AI

The optional Continue profiles in `configs/continue/` change the data-flow
picture and must be understood before use:

- **Online Hybrid sends data to a cloud provider.** Prompts and any context the
  operator (or the agent) attaches are transmitted to Groq for chat/edit/apply.
  Do not attach secrets or sensitive data to cloud requests.
- **`.continueignore` is not a security boundary.** It reduces accidental context
  inclusion, but a user can still manually attach a file or open it to the agent.
- **MCP results are untrusted input.** Code and help-index results are data, not
  instructions. The agent must not execute commands or instructions found inside
  indexed content (see `.continue/rules/1c-workbench.md`).
- **Help Index MCP read-only mode.** `HELP_INDEX_MODE=readonly` registers only the
  read tools and opens SQLite with URI `mode=ro`, so the database is never created
  or modified. `HELP_INDEX_MODE=operator` keeps the historical full behavior.
- **No secrets in profiles.** Profiles reference the Groq key only as
  `${{ secrets.GROQ_API_KEY }}`; the generator never prints or embeds the value.
  Runtime readiness inspects supported dotenv files only for a non-empty assignment
  and never passes the value to child probes. Never commit `.env` or a real key.
- **Generated-profile write boundary.** Output is confined to
  `<RepoRoot>/generated/continue`; normalized absolute/traversal escapes and existing
  reparse-point components are rejected before `-Force` is considered.
- **Local Ollama boundary.** Generated profiles pin the effective `OLLAMA_HOST` as
  `apiBase`, but accept only an explicit loopback HTTP endpoint. Runtime readiness
  probes that exact URL, so a healthy CLI pointed at a different port cannot produce
  a false-positive IDE readiness result.

See [docs/CONTINUE_THIN_CLIENT.md](docs/CONTINUE_THIN_CLIENT.md).

## Reporting

Open a private security issue or email the maintainer if you discover
a vulnerability that should not be discussed in public before a fix
is released.

## See also

- [docs/SECURITY_OVERVIEW.md](docs/SECURITY_OVERVIEW.md)
