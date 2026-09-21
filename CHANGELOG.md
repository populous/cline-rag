# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-09-21

### Added

- `ask.py`: MCP (Cline) registration management options, so users no longer
  have to hand-edit `cline_mcp_settings.json`:
  - `--mcp-print` prints the JSON snippet to add, with this project's
    actual `.venv` python path and `rag_server.py` path already filled in.
  - `--mcp-status [--mcp-settings PATH]` checks whether `cline-rag` is
    registered in Cline's settings file, and flags mismatched paths,
    missing `.venv`, or `disabled: true`.
  - `--mcp-install [--force] [--mcp-settings PATH]` merges the entry into
    the settings file directly (creating the file/parent dirs if needed),
    preserving any other already-registered MCP servers. Refuses to
    overwrite an existing `cline-rag` entry unless `--force` is given.
  - The `query` positional argument is now optional (`nargs="?"`) so these
    `--mcp-*` options can be used without also passing a question.
  - Covered by 7 new tests in `tests/test_ask_cli.py`.
- `ask.ps1` / `ask.cmd`: fix Korean text getting mangled when the script's
  stdout is piped, redirected to a file, or captured by the caller.
  PowerShell interprets a native process's stdout using `$OutputEncoding` /
  `[Console]::OutputEncoding`, which is independent of the console codepage
  (`chcp`) and is not UTF-8 by default on Korean Windows. The launchers now
  force both to UTF-8 at startup, so `.\ask.ps1 "질문"` renders correctly on
  screen and in redirected output regardless of the caller's terminal setup.
- `GETTING_STARTED.md` / `README.md`: reorganized so the terminal CLI
  (`ask.ps1` / `ask.cmd`) is presented as the primary, lowest-friction way to
  use this project. Registering the MCP server for Cline chat is now an
  explicit, clearly-labeled optional step, instead of being interleaved with
  the CLI instructions. This addresses confusion where "run this Python
  script to see a MCP tool response" was mistaken for "Cline answers
  immediately in chat" -- they are two different entry points into the same
  `rag_core.search_documents()` code path.
- `ask.ps1` (and `ask.cmd` for cmd.exe): launcher scripts that always run
  `src/ask.py` through the project's `.venv` interpreter, regardless of
  what `python` resolves to on the caller's PATH. This avoids the
  confusing `ModuleNotFoundError: No module named 'langchain_community'`
  that happens when someone runs `python src\ask.py` with a system
  Python instead of `.venv\Scripts\python.exe`.
- `src/ask.py` now detects that exact mis-launch (system Python missing
  the LangChain/LangGraph/Chroma stack) and prints a clear Korean
  explanation with the correct command to run, instead of a raw
  traceback.
- `src/ask.py`: a plain CLI to query the index directly from a terminal,
  without going through MCP/JSON-RPC or a subprocess wrapper. The query is
  passed as a command-line argument (not piped), so it is immune to the
  Windows console codepage/pipe-encoding issues that broke earlier
  copy-pasted examples. Supports `--top-k`, `--mode`, `--min-score`,
  `--sources`, `--config` and `--json`. Internally calls the exact same
  `rag_core.search_documents()` path that `rag_server.py`'s `search_docs`
  tool uses, so results are identical to what Cline would see.
- `tests/test_ask_cli.py` and the `rag.cli` CTest test covering it.

### Breaking

- Migrated the RAG core from a zero-dependency (standard-library-only)
  implementation to **LangChain + LangGraph**:
  - Embeddings: `langchain_ollama.OllamaEmbeddings` /
    `langchain_openai.OpenAIEmbeddings` (replaces the hand-rolled
    `urllib` HTTP calls)
  - Vector store: `langchain_chroma.Chroma`, persisted locally under
    `rag_store_chroma/` (replaces the `rag_store.sqlite3` file; the two
    formats are **not** compatible, run `ingest.py --reset` to reindex)
  - Chunking: `langchain_text_splitters.RecursiveCharacterTextSplitter`
    (replaces the hand-rolled paragraph-aware chunker; `chunk_text()` is
    kept as a thin wrapper for compatibility)
  - Keyword search: `langchain_community.retrievers.BM25Retriever` +
    `rank_bm25`, still driven by the project's own CJK bigram tokenizer
  - Search orchestration: a `langgraph.graph.StateGraph` that routes
    `vector`/`keyword`/`hybrid` modes through dedicated nodes and
    conditional edges (replaces the if/elif dispatch in
    `search_documents()`)
- `config.json` `store.path` now points to a Chroma persist directory
  instead of a SQLite file; `store.dim` was removed (Chroma manages
  embedding dimensionality itself)
- `SERVER_VERSION` bumped to `2.0.0` to signal the breaking storage
  format change
- `requirements.txt` now lists real third-party dependencies
  (`langchain-core`, `langchain-text-splitters`, `langchain-chroma`,
  `chromadb`, `langchain-ollama`, `langchain-openai`,
  `langchain-community`, `rank_bm25`, `langgraph`); the "zero
  dependency" design note no longer applies
- `requirements-optional.txt` dropped `numpy` (now a transitive
  dependency of `chromadb`)

### Why LangChain + LangGraph

- **Standardised embedding providers**: `OllamaEmbeddings` and
  `OpenAIEmbeddings` share the same `Embeddings` interface
  (`embed_documents` / `embed_query`), removing the hand-rolled
  `urllib` request/response handling per provider. Adding another
  provider (Bedrock, HuggingFace, ...) is now a matter of implementing
  that same interface.
- **A battle-tested vector store**: `Chroma` provides an HNSW index,
  metadata filtering (`where`), and collection-level upsert/delete out
  of the box — faster and less bug-prone at scale than a linear-scan
  cosine loop over a hand-rolled SQLite/JSON vector store.
- **More robust chunking**: `RecursiveCharacterTextSplitter` recursively
  splits on a prioritised separator list (`\n\n` -> `\n` -> sentence ->
  space -> character), a strategy that is widely used and tested across
  the community, handling edge cases (code blocks, lists, mixed-script
  text) more reliably than the previous hand-rolled paragraph splitter.
- **Explicit, inspectable search flow**: the if/elif dispatch inside
  `search_documents()` became a `StateGraph` with dedicated nodes and
  conditional edges per mode, making the vector/keyword/hybrid paths
  independently testable and visualisable (e.g. `get_graph()`), and
  easier to extend later (reranking node, query-expansion node, etc.)
- **Ecosystem reuse**: swapping in other LangChain document loaders
  (`PyPDFLoader`, ...) or vector stores (FAISS, Pinecone, ...) no longer
  requires rewriting project-specific code — only the LangChain
  component changes, benefiting from community-maintained bug fixes.
- **Easier testing**: a single deterministic fake implementing
  `langchain_core.embeddings.Embeddings` now exercises the whole
  pipeline (embed -> Chroma -> search) without Ollama/OpenAI, keeping
  CI free of external services.
- **Trade-off**: the "zero dependency" design goal is gone and
  `chromadb` adds noticeable install/CI time (CTest timeouts raised
  from 600s to 1200s). The MCP transport itself (stdio JSON-RPC) is
  still a direct standard-library implementation.

### Notes

- The MCP tool surface (`search_docs`, `list_indexed_sources`,
  `index_status`, `reindex`) and their input schemas are unchanged;
  only the implementation behind them moved to LangChain/LangGraph
- `tests/conftest.py` now provides a deterministic fake
  `langchain_core.embeddings.Embeddings` implementation instead of a
  bare function, so tests still run without Ollama/OpenAI

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

[Unreleased]: https://github.com/populous/cline-rag/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/populous/cline-rag/releases/tag/v2.0.0
[1.1.0]: https://github.com/populous/cline-rag/releases/tag/v1.1.0
[1.0.0]: https://github.com/populous/cline-rag/releases/tag/v1.0.0