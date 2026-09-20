# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-09-20

Keyword and hybrid retrieval, plus an in-chat reindex tool.

### Added

- `search_docs` gained two optional arguments:
  - `mode`: `hybrid` (default), `vector` or `keyword`
  - `sources`: restrict the search to specific indexed files
- BM25 keyword search over stored chunks, with CJK bigram tokenisation so
  Korean text is searchable without a morphological analyser
- Reciprocal Rank Fusion that merges the vector and keyword rankings, so
  cosine similarity (0..1) and BM25 (unbounded) never need calibrating
- `reindex` MCP tool that runs `ingest.py` in a child process
  (`paths`, `reset`), keeping the MCP stdout channel clean
- `tests/test_hybrid_search.py` covering tokenisation, BM25, RRF and modes
- MCP tests for the new arguments and the `reindex` tool

### Changed

- `search_docs` now defaults to `hybrid` instead of pure vector search;
  pass `mode="vector"` for the previous behaviour
- `search_docs` output now reports the mode that was used
- Core retrieval moved behind `rag_core.search_documents()`, which
  dispatches on the mode (`semantic_search()` is kept for compatibility)
- `sqlite3` row loading is shared through `rag_core.fetch_chunks()`

### Notes

- `min_score` applies to the vector ranker only: after fusion the score is
  rank-based, so a cosine threshold no longer has the same meaning
- `reindex` is a write tool, so it must **not** be added to `autoApprove`
- No new dependencies: tokenisation, BM25 and RRF are pure standard library

## [1.0.0] - 2026-09-20

First public release of the Cline RAG MCP server.

### Added

- MCP stdio server exposing three tools:
  `search_docs`, `list_indexed_sources`, `index_status`
- Embedding providers: local Ollama (`nomic-embed-text`) and OpenAI
  (`text-embedding-3-small`), selectable in `config.json`
- SQLite vector store with cosine similarity search implemented in pure Python
- `src/ingest.py` indexing CLI with `--reset`, `--prune`, `--stats`, `--list`,
  and `--provider` options
- Paragraph-aware chunking with configurable size and overlap
- 49 pytest tests covering chunking, similarity, store CRUD, ranking,
  and the MCP protocol (no external services required)
- CMake test pack that wraps pytest as CTest tests:
  `rag.unit`, `rag.mcp`, `rag.smoke`
- One-command setup script (`setup.ps1`) and step-by-step guide
  (`RAG_STEP_BY_STEP.md`)
- `.clinerules` template so Cline searches before answering

### Fixed

- Force UTF-8 on stdout/stderr in `smoke_mcp.py` and `src/ingest.py` so the
  Windows CI runner (cp1252 console) no longer fails with
  `UnicodeEncodeError` when printing Korean status lines

### Notes

- Zero third-party runtime dependencies (standard library only)
- MCP handled directly over stdio JSON-RPC; no web framework
- Verified on Python 3.14.7 with CMake/CTest 4.4.3 on Windows
- CI runs on windows-latest with Python 3.12 (pytest + smoke + CTest)

[Unreleased]: https://github.com/populous/cline-rag/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/populous/cline-rag/releases/tag/v1.1.0
[1.0.0]: https://github.com/populous/cline-rag/releases/tag/v1.0.0