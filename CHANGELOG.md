# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/populous/cline-rag/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/populous/cline-rag/releases/tag/v1.0.0