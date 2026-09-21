# cline_rag

[![CI](https://github.com/populous/cline-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/populous/cline-rag/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/populous/cline-rag)](https://github.com/populous/cline-rag/releases)

Cline 에 붙이는 **로컬 RAG 검색 MCP 서버**. v2.0.0부터 **LangChain + LangGraph** 기반으로
동작합니다(임베딩 · Chroma 벡터 저장소 · 청킹 · 검색 오케스트레이션).

**처음 사용하시나요?** **[GETTING_STARTED.md](GETTING_STARTED.md)** 에서
설치부터 Cline 등록까지 순서대로 따라 하세요.

전체 구축 과정은 **[RAG_STEP_BY_STEP.md](RAG_STEP_BY_STEP.md)**  보세요.
변경 이력은 **[CHANGELOG.md](CHANGELOG.md)** 에 있습니다.

## 구성

```
cline_rag/
├── src/                       # 소스
│   ├── rag_core.py            # 임베딩(Ollama/OpenAI) + Chroma 벡터 저장소
│   │                          # + RecursiveCharacterTextSplitter + BM25 + LangGraph 검색
│   ├── ingest.py              # 문서 -> 청크 -> 임베딩 -> Chroma 색인 CLI
│   └── rag_server.py          # MCP stdio 서버 (도구 4개)
├── tests/                     # pytest 테스트
│   ├── conftest.py            # 공용 픽스처 (외부 서비스 불필요, 가짜 Embeddings)
│   ├── test_rag_core.py       # 코어 단위 테스트
│   ├── test_hybrid_search.py  # 토크나이저/BM25/RRF/검색 모드 테스트
│   └── test_mcp_server.py     # MCP 프로토콜/도구 테스트
├── docs/                      # 색인할 문서
├── CMakeLists.txt             # 테스트 패킹 유틸 (pytest -> CTest 래핑)
├── CMakePresets.json          # default / ninja / ci 프리셋
├── pytest.ini                 # pytest 설정
├── config.json                # 임베딩 제공자 / Chroma 저장소 / 청킹 설정
├── smoke_mcp.py               # 서버를 자식 프로세스로 띄우는 스모크 검사
├── setup.ps1                  # venv + 의존성 + 색인 + 테스트 (원클릭)
├── requirements.txt           # 런타임 의존성 (LangChain/LangGraph/Chroma)
├── requirements-dev.txt       # 테스트 의존성 (pytest)
├── requirements-optional.txt  # 선택 확장 (pypdf)
├── requirements.lock.txt      # pip freeze 기록
└── GETTING_STARTED.md         # 처음 사용자용 매뉴얼
```

## 빠른 시작

한 번에 설정 + 검증:

```powershell
cd C:\path\to\cline_rag
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

수동으로 하려면:

```powershell
cd C:\path\to\cline_rag

python -m venv .venv                              # 1) 가상환경
.\.venv\Scripts\Activate.ps1                       # 2) 활성화
python -m pip install --upgrade pip                # 3) pip 최신화
python -m pip install -r requirements.txt          # 4) 런타임 의존성 (LangChain/LangGraph/Chroma)
python -m pip install -r requirements-dev.txt      # 5) pytest

ollama pull nomic-embed-text                       # 6) 임베딩 모델 (최초 1회)
python src\ingest.py --reset                       # 7) 인
python smoke_mcp.py                                # 8) MCP 스모크 검사
python -m pytest tests -q                          # 9) 테스트
```

## CMake 테스트 팩 (pytest -> CTest 래핑)

CMake 를 **컴파일이 아니라 테스트 패킹 유틸** 로만 씁니다(`LANGUAGES NONE`).

```powershell
# 프리셋으로
cmake --preset default        # 격리된 build/test-venv 생성 + pytest 설치
ctest --preset default        # 전체 테스트 팩
ctest --preset unit           # 단위 테스트만
ctest --preset mcp            # MCP 테스트만

# 프리셋 없이
cmake -S . -B build
ctest --test-dir build -C Debug --output-on-failure
ctest --test-dir build -C Debug -L mcp        # 라벨 필터
ctest --test-dir build -C Debug --show-only   # 등록된 테스트 목록

# 한 번에 (빌드 타깃)
cmake --build build --config Debug --target test-pack
```

등록되는 CTest 테스트:

| 테스트 | 실행 내용 | 라벨 |
|---|---|---|
| `rag.unit` | `pytest tests/test_rag_core.py -v` | `rag;unit` |
| `rag.hybrid` | `pytest tests/test_hybrid_search.py -v` | `rag;unit;hybrid` |
| `rag.mcp` | `pytest tests/test_mcp_server.py -v` | `rag;mcp;protocol` |
| `rag.smoke` | `smoke_mcp.py` (자식 프로세스 핸드셰이크) | `rag;smoke` |

CMake 옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `CLINE_RAG_SETUP_TEST_ENV` | `ON` | 격리된 `build/test-venv` 생성 + 테스트 의존성 설치 |
| `BUILD_TESTING` | `ON` | `include(CTest)` 가 정의 |

이미 설치된 venv 를 재사용하려면:

```powershell
cmake -S . -B build-ninja -G Ninja -DCMAKE_BUILD_TYPE=Debug `
  -DCLINE_RAG_SETUP_TEST_ENV=OFF `
  -DPython3_EXECUTABLE="$PWD\.venv\Scripts\python.exe"
ctest --test-dir build-ninja --output-on-failure
```

## 의존성

| 파일 | 내용 | 설치 시점 |
|---|---|---|
| `requirements.txt` | 런타임 — LangChain/LangGraph/Chroma 등 | 항상 |
| `requirements-dev.txt` | `pytest>=8.0` | 테스트/CMake |
| `requirements-optional.txt` | `pypdf` | 필요할 때만 |

핵심 런타임 의존성(`requirements.txt`):

```
langchain-core, langchain-text-splitters, langchain-chroma, chromadb,
langchain-ollama, langchain-openai, langchain-community, rank_bm25, langgraph
```

* **임베딩**: `langchain_ollama.OllamaEmbeddings` / `langchain_openai.OpenAIEmbeddings`
* **벡터 저장소**: `langchain_chroma.Chroma` (로컬 디스크 영속, 별도 서버 불필요)
* **청킹**: `langchain_text_splitters.RecursiveCharacterTextSplitter`
* **키워드 검색**: `langchain_community.retrievers.BM25Retriever` + `rank_bm25`
  (CJK bigram 토크나이저는 자체 구현)
* **검색 오케스트레이션**: `langgraph.graph.StateGraph` 로 vector/keyword/hybrid 모드를
  노드/조건부 엣지로 분기
* MCP 서버(stdio JSON-RPC)는 여전히 표준 라이브러리로 직접 구현했습니다
  (별도 웹 프레임워크 불필요).

선택 확장이 필요할 때만:

```powershell
python -m pip install -r requirements-optional.txt   # pypdf
```

## 제공 도구

| 도구 | 설명 |
|---|---|
| `search_docs(query, top_k, min_score, sources, mode)` | 문서 검색. `mode`=hybrid(기본)/vector/keyword, `sources` 로 파일 제한 |
| `list_indexed_sources()` | 색인된 파일 목록 |
| `index_status()` | 색인 현황(청크/파일/차원) |
| `reindex(paths, reset)` | 문서 재색인 (쓰기 도구, `autoApprove` 제외) |

## 검색 모드

`search_docs` 는 `mode` 로 검색 방식을 고릅니다.

| mode | 방식 | 사용 시점 |
|---|---|---|
| `hybrid` (기본) | 벡터 + BM25 를 RRF 로 합치 | 대부분의 질문 |
| `vector` | 코사인 유사도(의미) | 표현이 달라도 의미로 찾을 때 |
| `keyword` | BM25(정확한 용어) | 함수명·에러코드 등, 임베딩 호출 없이 빠름 |

- `sources` 로 색인된 파일 일부만 좁힙니다.
- 주의: `hybrid`/`keyword` 의 점수는 RRF 순위 점수라
  `min_score`(코사인 하한)가 적용되지 않습니다.
  임계값이 필요하면 `mode="vector"` 를 쓰세요.

## Cline 등록

`C:\Users\<you>\.cline\data\settings\cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "cline-rag": {
      "command": "C:\\path\\to\\cline_rag\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\cline_rag\\src\\rag_server.py"],
      "env": {},
      "disabled": false,
      "autoApprove": ["search_docs", "list_indexed_sources", "index_status"]
    }
  }
}
```

> 시스템 `python` 대신 **`.venv\Scripts\python.exe`** 를 쓰는 이유:
> 환경이 격리되고 경로가 고정됩니다. 특히 이 PC 는 `python` 이
> Windows Store 셰임(`WindowsApps\python.exe`)을 가리켜서 그대로 쓰면
> MCP 기동에 실패할 수 있습니다.

## 명령 요약

```powershell
# 색인
python src\ingest.py                 # 증분 색인
python src\ingest.py --reset         # 전체 재색인
python src\ingest.py --prune         # 삭삭제된 파일 청크 제거
python src\ingest.py --stats         # 현황
python src\ingest.py --list          # 색색인된 파일 목록

# 테스트
python smoke_mcp.py                  # MCP 스모크 (자식 프로세스)
python -m pytest tests -q            # pytest 전체
cmake --preset default ; ctest --preset default   # CMake/CTest 테스트 팩
```

## 버전 관리 (Git / GitHub)

이 저장소는 `populous/cline-rag` 이고 `main` 을 기본 브랜치로 씁니다.

```powershell
# 브랜치 -> 커밋 -> PR -> CI -> 병합
git switch -c feat/hybrid-search
git commit -m "feat: add BM25 hybrid search"
git push -u origin feat/hybrid-search
gh pr create --base main --fill
gh pr checks --watch
gh pr merge --squash --delete-branch
```

| 항목 | 규칙 |
|---|---|
| 브랜치 | `feat/…` `fix/…` `docs/…` `test/…` `chore/…` `release/…` |
| 커밋 | Conventional Commits (`feat:`, `fix:`, `docs:`, `chore(release):`) |
| 병합 | 기본 `--squash`, 릴리스 경계는 `--merge`, main 최신화는 `--ff-only` |
| 버전 | SemVer. 단일 출처는 `src/rag_server.py` 의 `SERVER_VERSION` |
| 릴리스 | `main` 에 태그 + `gh release create` |
| 변경 이력 | `CHANGELOG.md` (Keep a Changelog) |

릴리스 절차:

```powershell
git switch -c release/v1.1.0
# SERVER_VERSION 과 CHANGELOG 갱신
python -m pytest tests -q
git commit -m "chore(release): v1.1.0"
git push -u origin release/v1.1.0
gh pr create --base main --title "chore(release): v1.1.0" --fill
gh pr merge --merge --delete-branch

git switch main; git pull --ff-only
git tag -a v1.1.0 -m "v1.1.0"
git push origin main --follow-tags
gh release create v1.1.0 --title "v1.1.0" --generate-notes
```

전체 명령과 트러블슈팅은 **[RAG_STEP_BY_STEP.md](RAG_STEP_BY_STEP.md)** 13장을 보세요.

## 설계 메모

- **LangChain + LangGraph 기반(v2.0.0)**: 임베딩/벡터 저장소/청킹/키워드 검색은
  LangChain 컴포넌트로, 검색 오케스트레이션(모드 분기)은 LangGraph `StateGraph` 로
  구현합니다. MCP 프로토콜 자체는 여전히 표준 라이브러리로 직접 구현합니다.
- **src 레이아웃**: 소스는 `src/`, 데이터(`config.json`, `rag_store_chroma/`)는 프로젝트
  루트에 둡니다. `rag_core.PROJECT_DIR` 이 기준을 결정합니다.
- **MCP 직접 구현**: `initialize`, `ping`, `tools/list`, `tools/call` 만 구현한 최소 stdio JSON-RPC 서버입니다.
- **stdout 은 프로토콜 전용**: 로그는 전부 stderr(UTF-8 고정)로 나갑니다.
- **경로 해석 단일화**: 네 도구가 `load_config_and_store()` 하나만 써서 경로 기준이 어긋날 수 없습니다.
- **임베딩 모델 고정**: 색인 후 모델을 바꾸면 벡터 공간이 달라지므로 `--reset` 이 필요합니다.
- **테스트는 외부 서비스 불필요**: `conftest.py` 가 `langchain_core.embeddings.Embeddings` 를
  구현한 결정적 가짜 임베딩으로 바꿔 Ollama/OpenAI 없이 돕니다.
- **저장소 포맷 변경(breaking)**: v1.x 의 `rag_store.sqlite3` 는 v2.0.0 의 Chroma
  저장소(`rag_store_chroma/`)와 호환되지 않습니다. `ingest.py --reset` 으로 재색인하세요.