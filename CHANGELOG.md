# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.4.1] - 2026-09-24

### Added

- `examples/06_ollama_gpu/` — Ollama GPU(PTX/CUDA) 임베딩 검증 도구:
  `check_ollama_gpu.py`(읽기 전용 PASS/FAIL 진단, PTX 오류 감지,
  `--require-gpu` 플래그, nvidia-smi + `/api/ps` 로 GPU/CPU 러너 판별)와
  드라이버 업데이트 후 확인 절차를 담은 README 추가

## [2.4.0] - 2026-09-23

### Added

- Advanced RAG orchestration graph (LangGraph StateGraph): hybrid_retrieve -> rerank -> emit_metrics
- Cross-encoder reranking node (sentence-transformers, RERANKER_MODEL env var)
- LangSmith tracing/performance metrics schema (RetrievalMetrics, RerankMetrics)
- tests/test_advanced_rag_graph.py (5 unit tests)

## [2.3.0] - 2026-09-23

### Added

- `examples/` learning labs: a self-contained, main-job-safe set of
  step-by-step tutorials covering the technologies behind `cline-rag`:
  - `01_llama_cpp` — GGUF loading, in-process/server embeddings, text generation
  - `02_langchain` — prompt templates, output parsers, LCEL, retrievers,
    llama.cpp as an LLM backend
  - `03_langgraph` — StateGraph, conditional routing, tool-calling loop,
    a retrieve+generate RAG graph
  - `04_langsmith` — tracing, LangGraph run tracing, eval datasets
  - `05_upgrade_path` — a roadmap and `benchmark_embeddings.py` for promoting
    llama.cpp to the main embedding engine
- `examples/requirements-examples.txt` keeps example-only dependencies
  (`llama-cpp-python`, `langsmith`, `python-dotenv`) separate from the main
  app requirements.

### Security

- `.env` added to `.gitignore` so the LangSmith API key is never committed;
  `examples/.env.example` is a committed, keyless template.

## [2.2.0] - 2026-09-23

### Added

- llama.cpp embedding providers: `llama_cpp` (in-process, loads a GGUF model
  via `llama-cpp-python`) and `llama_cpp_server` (calls the OpenAI-compatible
  `/v1/embeddings` endpoint exposed by `llama-server`, reusing
  `langchain-openai` with no new dependency). `rag_core.build_embeddings()`
  delegates both to `src/embeddings_llama_cpp.py`; defaults live in
  `DEFAULT_CONFIG["embedding"]`. `llama-cpp-python` added to
  `requirements-optional.txt` (only for the in-process provider), with
  `tests/test_embeddings_llama_cpp.py` (6 cases, no external services) and
  `docs/llama_cpp_provider.md`.
- `GETTING_STARTED.md` 7단계에 "새로 설치 시 필요한 의존성 한눈에 보기" 표를
  추가: 시스템에 미리 설치해야 하는 것(Python, Git, Ollama, OpenCode/Cline)과
  `requirements*.txt` 별 Python 패키지 목록(필수/선택 구분)을 한 곳에 정리.
- `GETTING_STARTED.md` 4단계에 "OpenCode 창을 열어서 실제로 확인하기" 절
  추가: `opencode` 명령으로 TUI를 열고, MCP 연결 상태를 확인하고, 자연어
  질문만으로 OpenCode 가 `search_docs` 를 자동 호출해 문서 근거로 답하는지
  검증하는 구체적인 절차를 기록. 실제로 OpenCode 창에서 MCP 연결과
  질의응답이 정상 동작함을 확인한 뒤 반영함.
- `ARCHITECTURE.md` 신규 추가: MCP(Model Context Protocol) 관점에서
  `cline-rag`(=MCP Server, `src/rag_server.py`)와 OpenCode/Cline(=MCP
  Host)의 관계를 정리. Host/Client/Server 3단 역할 분담, RAG의 검색(R)과
  생성(A+G)이 어느 쪽 책임인지, 도구별 autoApprove 가능 여부, "검색을
  먼저 한다"는 규칙이 MCP 프로토콜이 아니라 Host가 로드하는 규칙
  파일(`AGENTS.md`/`clinerules-template.md`)에서 오는 것이라는 점을
  명시. README.md/GETTING_STARTED.md 에서 링크로 연결.
- `ARCHITECTURE.md`에 "MCP 호스트에 가져가야 할 파일들" 절 추가: 새
  머신에서 OpenCode/Cline이 `cline-rag`를 MCP 서버로 쓰려면 저장소를
  통째로 clone해야 하는 이유(`rag_server.py`가 `rag_core.py`에 의존하고
  `PROJECT_DIR` 기준으로 `config.json`/`docs/`를 찾음)와, 반대로
  `.venv/`·`rag_store_chroma/`·Host 등록 설정처럼 git에 없어서 머신마다
  새로 만들어야 하는 3가지 항목을 표로 정리.
- `ARCHITECTURE.md` 흐름도 보강: Ollama 엔진이 "색인(문서→벡터 저장)과
  검색(질의→벡터 비교) 모두에 개입"하는 핵심 엔진임을 명시하고, 색인
  단계 다이어그램을 추가. vector/keyword/hybrid 모드별 Ollama 개입
  여부와 BM25(keyword)는 검색 시 Ollama 없이 텍스트 빈도로만 계산된다는
  점을 표로 정리.
- `ARCHITECTURE.md`에 "로컬 엔진별 색인/검색 능력 차이" 절 추가: 4개
  로컬 엔진(Ollama, Chroma, BM25/rank_bm25, LangGraph) 각각의 색인/검색
  관여 여부를 표와 관여 지도로 정리. Ollama+Chroma 만 색인에 관여하고,
  BM25는 검색 시점 즉석 계산(자체 저장소 없음), LangGraph는 오케스트레이션
  전담임을 명시.

## [2.1.0] - 2026-09-21

### Added

- OpenCode (opencode.ai) support across the project, making OpenCode the
  primary MCP client alongside Cline:
  - `AGENTS.md` at the repo root: OpenCode auto-loads these search-first rules
    (call `search_docs` before answering, cite sources, never fabricate, get
    approval before `reindex`), plus a build/test/run command reference.
  - `ask.py` gained `--mcp-target cline|opencode` (default `cline`). With
    `opencode`, `--mcp-print`/`--mcp-status`/`--mcp-install` target
    `~/.config/opencode/opencode.json` and emit the OpenCode shape
    `{"mcp": {"cline-rag": {"type": "local", "command": ["<venv python>", "<rag_server.py>"], "enabled": true}}}`
    instead of Cline's `mcpServers`/`command`+`args` form.
  - `setup.ps1` prints OpenCode registration instructions.
- Documentation migrated to OpenCode-first (`README.md`, `GETTING_STARTED.md`,
  `RAG_STEP_BY_STEP.md` §7/§8), with Cline kept as a documented legacy path.

### Changed

- `rag_server.py` `reindex` tool description now warns against adding it to
  auto-approval lists generically (`autoApprove`/`permission allow`) rather
  than naming Cline's `autoApprove` only.

### Notes

- 5 new `tests/test_ask_cli.py` cases cover the OpenCode print/status/install
  path (no external services). Existing Cline `--mcp-*` behavior is unchanged
  and still covered.
- The MCP server name `cline-rag` and store directory names are unchanged
  (renaming is intentionally out of scope for this migration).

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

[Unreleased]: https://github.com/populous/cline-rag/compare/v2.4.1...HEAD
[2.4.1]: https://github.com/populous/cline-rag/releases/tag/v2.4.1
[2.4.0]: https://github.com/populous/cline-rag/releases/tag/v2.4.0
[2.3.0]: https://github.com/populous/cline-rag/releases/tag/v2.3.0
[2.2.0]: https://github.com/populous/cline-rag/releases/tag/v2.2.0
[2.1.0]: https://github.com/populous/cline-rag/releases/tag/v2.1.0
[2.0.0]: https://github.com/populous/cline-rag/releases/tag/v2.0.0
[1.1.0]: https://github.com/populous/cline-rag/releases/tag/v1.1.0
[1.0.0]: https://github.com/populous/cline-rag/releases/tag/v1.0.0