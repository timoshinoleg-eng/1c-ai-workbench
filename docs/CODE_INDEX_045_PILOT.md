# code-index-mcp 0.45.0 Pilot Report

## Verdict

`code-index-mcp` 0.45.0 passed the isolated pilot and is accepted as the pinned
workbench vendor version. The source boundary is upstream tag `v0.45.0`, commit
`a0869e71767207aafa18e9d6c6abaddfb0555589`.

The default product boundary remains local and read-only. The upstream Docker
deployment files are retained as vendor source but are not enabled or installed
by the workbench.

## Test corpus and binaries

- Corpus: `C:\1c-ai-demo`, 352 source files, including 69 BSL files.
- Baseline: `code-index 0.42.2` from the previous pinned vendor.
- Candidate: `code-index 0.45.0`, release build from the pinned upstream tag.
- Each version indexed a separate byte-identical copy with an independent
  `.code-index` database and `CODE_INDEX_HOME`.

## Performance

| Measurement | 0.42.2 | 0.45.0 | Delta |
| --- | ---: | ---: | ---: |
| Full index wall time | 2,216 ms | 2,033 ms | -8.3% |
| Full index peak working set | 24.1 MB | 24.4 MB | +1.2% |
| One-file incremental wall time | 1,524 ms | 1,468 ms | -3.7% |
| One-file incremental peak working set | 24.6 MB | 24.3 MB | -1.2% |

No performance or memory measurement exceeded the 15% regression threshold.
These numbers are a same-host pilot, not a general throughput benchmark.

## Golden index comparison

| Entity | 0.42.2 | 0.45.0 | Assessment |
| --- | ---: | ---: | --- |
| Indexed files | 337 | 336 | Intentional: `ConfigDumpInfo.xml` moved from generic text indexing to `config_manifest` |
| Functions/procedures | 396 | 396 | Equal |
| Classes/objects | 84 | 84 | Equal |
| Variables | 220 | 220 | Equal |
| Calls | 1,664 | 1,565 | Intentional noise removal for BSL constructors such as `Новый Массив` |
| Metadata objects | 102 | 102 | Equal |
| Metadata modules | 47 | 66 | Intentional improved module reconciliation |
| Data links | 228 | 228 | Equal |
| Metadata code usages | 200 | 200 | Equal |
| Configuration manifest | unavailable | 557 | New contract populated from `ConfigDumpInfo.xml` |

The exact function lookup for `обновитьСуммуДокумента` preserved all three
procedures. The exact body search for `Движения.Продажи` preserved both expected
procedures and line evidence. Search results no longer surface the service file
`ConfigDumpInfo.xml`; the next user-facing XML hit is returned instead.

Parser-driven line starts move by one line for procedures preceded by a compile
directive because the directive is now metadata (`return_type`) rather than part
of the procedure body. This is an intentional semantic correction.

## Incremental and manifest contract

After changing one BSL module, the incremental database was compared with a
clean full rebuild of the same changed source. Semantic row counts and SHA-256
digests matched for all nine extended tables:

- `data_links`;
- `metadata_objects`;
- `config_manifest`;
- `metadata_modules`;
- `metadata_forms`;
- `role_rights`;
- `event_subscriptions`;
- `metadata_code_usages`;
- `proc_call_graph`.

The provider-free gate `scripts/25_validate_code_index_045.py` repeats the
golden lookup, constructor-call exclusion, two-row manifest contract, and the
nine-table incremental/full parity check on a committed miniature 1C fixture.
CI and the signed release workflow run this gate against the exact release
binary.

## Upstream and workbench verification

- Upstream workspace tests: 581 passed, 0 failed; one documentation example is
  intentionally ignored.
- The first parallel debug build hit Windows `os error 1455` because the host
  pagefile was too small. Re-running with `CARGO_BUILD_JOBS=1` passed. This is a
  host resource constraint, not a source failure.
- Local workbench hardening retained: four Clippy fixes and safe API-key
  placeholders in two vendor documents.
- The rebuilt Windows binary reports `code-index 0.45.0`.

## Remaining release dependency

The vendor upgrade does not remove the external production blocker. A public RC
still requires the real Authenticode certificate, a green signed release run,
and SmartScreen verification on a clean Windows host.
