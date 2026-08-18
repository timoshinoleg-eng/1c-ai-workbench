# Feature-Gap Map: Search and Metadata

**Purpose:** avoid duplicating capabilities already present in the vendored `tools/code-index-mcp` source tree before planning new MCP tools. This inventory is a product-planning artifact; it does not claim a capability is enabled in every packaged `bsl-indexer` build until verified against its release version and feature flags.

## Inventory

| Capability requested by audit/competitors | Current evidence | Status | Next action |
|---|---|---|---|
| SQLite FTS5 | `README_RU.md` describes FTS5 index and MCP search tools | Present | Add focused ranking regression cases, not a second search engine |
| BM25 ranking | Needs release-binary/source tool-contract verification; do not assume based only on FTS5 | Unknown in workbench profile | Create corpus and inspect exposed search parameters before implementation |
| RU↔EN BSL aliases | XML object synonyms exist; language keyword alias expansion is not yet demonstrated in workbench docs/tests | Partial | Add only a provenance-tracked alias layer if corpus confirms a recall gap |
| `get_object_profile` / metadata inspection | BSL extension source contains `get_object_profile` and object structure tooling | Present in source | Verify it is exposed in shipped `bsl-indexer`; document as primary metadata inspector if yes |
| `get_object_structure` | BSL extension source contains dedicated tool | Present in source | Verify release exposure; do not create a duplicate Python bridge |
| Subsystem navigation | Requires tool-contract confirmation rather than assumption from XML parser presence | Unknown | Inventory current MCP registry before adding `list_subsystems` |
| Object/data reference graph | README documents data-link graph, `get_data_links`, `find_data_path` and register writers | Present in source/profile docs | Benchmark packaged build before proposing a new `refs` schema |
| Call hierarchy | README documents BSL call graph and generic callers/callees | Present | Use existing tool in demo corpus |
| Semantic/vector search | No confirmed workbench default profile or local-model policy | Gap | Separate epic after privacy, hardware, evaluation and storage decisions |
| Query validation without live IB | No confirmed offline 1C query validator in workbench profile | Gap | Feasibility spike; define supported dialect/СКД boundaries first |
| Tool presets | No confirmed workbench-level profile gate | Gap | Small UX epic after complete registry inventory |
| `lint_module` via BSL Language Server | No integrated external process/JAR packaging evidence | Gap | Separate LGPL/dependency/offline delivery epic |
| Git hotspots/blame | No dedicated workbench bridge | Gap | Separate privacy/path-policy epic |

## Decisions for the next development cycle

1. **Do not implement graph dependencies, metadata profile, or generic call hierarchy from scratch.** The source/profile documentation indicates that the indexer already contains related BSL tooling.
2. **Do not promise BM25 or alias expansion** until the shipped binary and its MCP schema are inspected with a reproducible corpus.
3. **Prioritize a search regression corpus.** It should include exact BSL symbol queries, regex, Russian/English terminology, object synonyms, metadata fields and false-positive controls.
4. **Treat semantic search, linting and Git intelligence as independent product epics.** Each has a material privacy, licensing, distribution or operational decision.

## Verification tasks before a new search feature PR

| Check | Evidence required |
|---|---|
| Tool registry | `bsl-indexer` tool list/help or MCP introspection from the target release |
| Build feature flags | `Cargo.toml`, release build command and `--version`/feature output |
| Result quality | Versioned corpus with expected top-k results |
| Performance | Query latency and memory on representative XML dump |
| Compatibility | Existing MCP clients and default workbench configuration |
| Provenance | Source/license for any synonym or benchmark dataset |

## References

- [`tools/code-index-mcp/README_RU.md`](../tools/code-index-mcp/README_RU.md)
- [`tools/code-index-mcp/Cargo.toml`](../tools/code-index-mcp/Cargo.toml)
- [`docs/RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md)
