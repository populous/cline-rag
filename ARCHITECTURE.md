# 아키텍처: `cline-rag` 는 MCP 서버다

이 문서는 `cline-rag` 프로젝트를 **MCP(Model Context Protocol)** 관점에서
정리한다. "이 프로젝트가 정확히 무엇이고, OpenCode/Cline 같은 호스트와
어떤 관계인가"를 한 곳에서 확인하려면 이 문서를 보면 된다.

설치/사용법은 **[GETTING_STARTED.md](GETTING_STARTED.md)**, 구축 과정과
설계 배경은 **[RAG_STEP_BY_STEP.md](RAG_STEP_BY_STEP.md)** 를 참고한다.

---

## 핵심 명제: RAG는 MCP다

`cline-rag` 프로젝트 자체가 **하나의 MCP 서버**이고, 그 서버가 제공하는
도구(tool)들이 **RAG(검색 증강 생성)의 검색(Retrieval) 부분**을 구현한
것이다. 정리하면:

> **cline-rag = MCP 서버 (Server 역할)**
> **OpenCode / Cline = MCP 호스트 (Host 역할)**

## MCP 3단 구조로 본 역할 분담

MCP는 표준적으로 세 주체로 나뉜다. 이 프로젝트에서 각각이 누구인지는
다음과 같다.

| MCP 역할 | 하는 일 | 이 프로젝트에서 누구 | 근거 |
|---|---|---|---|
| **Host** | LLM을 실제로 돌리며 사용자와 대화하는 주체 | OpenCode, Cline | `opencode.json`, `cline_mcp_settings.json` 에 서버를 등록 |
| **Client** | Host 내부에서 서버 1개와의 연결을 관리하는 커넥터 | OpenCode/Cline 내장 MCP 클라이언트 | Host 프로그램 내부 구현(이 저장소 밖) |
| **Server** | 도구(tool)를 제공하는 쪽 | `src/rag_server.py` | 파일 최상단 주석: *"Cline/OpenCode 등 MCP 클라이언트에 붙이는 RAG MCP 서버"* |

`rag_server.py`는 **stdio 기반 JSON-RPC 2.0**을 표준 라이브러리만으로 직접
구현한 순수 MCP 서버다(별도 웹 프레임워크 없음). Host(OpenCode/Cline)가 이
서버를 **자식 프로세스로 실행**하고, stdin/stdout으로 JSON-RPC 메시지를
주고받는다. `stdout`은 프로토콜 전용이라, 로그는 전부 `stderr`로 나간다.

## 전체 흐름도

```
                     MCP 프로토콜(stdio, JSON-RPC 2.0)
[OpenCode/Cline]  ◄─────────────────────────────────►  [rag_server.py]
  (Host)                                                  (Server)
     │                                                        │
     │ tools/call: search_docs("연차일 수는?")                 │
     ├───────────────────────────────────────────────────────►│
     │                                                        ▼
     │                                          rag_core.search_documents()
     │                                          ├─ (vector) Ollama: 질문 → 벡터
     │                                          │     └─ Chroma: 코사인 유사도 검색
     │                                          └─ (keyword) BM25: 키워드 매칭
     │                                                └─ (hybrid 에서) RRF 로 융합
     │                                                        │
     │◄───────────────────────────────────────────────────────┤
     │  결과: docs/example_vacation_policy.md#chunk0 원문 발췌  │
     ▼
[Host의 LLM 이 이 발췌를 "증강된 컨텍스트"로 받아 최종 답변 생성]
  → "연차는 1년 차 15일, 3년 이상 근무 시 2년마다 1일 추가, 최대 25일..."
```

색인(서비스 시작 전 1회)에서도 Ollama 가 핵심 역할을 한다:

```
[원본 문서 docs/] → src/ingest.py → 청크 분할 → Ollama: 청크 → 벡터
                                                        │
                                                        ▼
                                          Chroma 벡터 저장소(rag_store_chroma/)
```

### Ollama 엔진의 역할: 색인과 검색에 모두 개입

Ollama 는 "텍스트 → 벡터"를 만드는 임베딩 엔진이며, **색인과 검색 두 단계
모두**의 핵심이다.

| 단계 | Ollama 가 하는 일 |
|---|---|
| **색인(Ingest/Index)** | `docs/` 문서를 청크로 나눈 뒤, 각 청크를 벡터로 변환해 Chroma 에 저장 |
| **검색(Search)** | 사용자 질의를 벡터로 변환해, 저장된 청크 벡터들과 코사인 유사도 비교 |

단, 검색 순위 계산 방식에 따라 Ollama 의 개입 여부가 나뉜다.

| 모드 | 색인 시 Ollama | 검색 시 Ollama | 실제 검색 방식 |
|---|---|---|---|
| `vector` | 필요 | 필요 | 코사인 유사도 |
| `hybrid` | 필요 | 필요(vector 쪽) | 코사인 + BM25 → RRF 융합 |
| `keyword` | 필요(색인은 항상 임베딩 저장) | 불필요 | BM25 키워드 매칭 |

> 핵심: **Ollama 는 색인과 벡터 검색의 핵심 엔진**이다. 다만 `keyword`
> (BM25) 모드의 "검색 순위 계산"만은 Ollama 없이 텍스트 빈도로 직접
> 수행된다. (그래서 `keyword` 모드는 임베딩 호출이 없어 빠르다.)

즉 **R(Retrieval)은 `rag_server.py`(MCP Server)가 담당**하고,
**A+G(Augmented Generation)는 Host(OpenCode/Cline)의 LLM이 담당**한다.
이 프로젝트 자체는 생성(Generation)을 하지 않고, MCP 프로토콜을 통해
"검색 결과"만 Host에 돌려준다.

## 제공하는 4개 도구 (MCP의 "기능 노출 단위")

| 도구 | 성격 | 자동 승인(autoApprove) | 정의 위치 |
|---|---|---|---|
| `search_docs` | 읽기 전용, RAG의 핵심(Retrieval) | ✅ 가능 | `src/rag_server.py` `TOOLS` |
| `list_indexed_sources` | 읽기 전용 | ✅ 가능 | 〃 |
| `index_status` | 읽기 전용 | ✅ 가능 | 〃 |
| `reindex` | **쓰기 도구**(색인 데이터 변경) | ❌ 금지, 항상 Host가 사용자 승인 요청 | 〃 |

`reindex`는 `ingest.py`를 자식 프로세스로 실행해서 색인 데이터를 바꾸는
쓰기 작업이므로, `autoApprove`(OpenCode의 `permission` allow 목록도 동일)
에 **절대 넣지 않는다**. 나머지 3개는 읽기 전용이라 자동 승인해도 안전하다.

## "검색이 먼저"는 프로토콜이 아니라 Host 쪽 규칙

MCP 서버(`rag_server.py`)는 도구를 **노출**할 뿐, 언제 호출할지는 전적으로
Host 쪽 결정이다. "질문에 답하기 전에 반드시 `search_docs`를 먼저
호출한다"는 행동 지침은 MCP 프로토콜 자체의 강제 사항이 아니라, Host가
로드하는 **규칙 파일**에 명시되어 있다.

| Host | 규칙 파일 |
|---|---|
| OpenCode | `AGENTS.md` (프로젝트 루트, 자동 로드) |
| Cline | `.clinerules/` (`clinerules-template.md` 참고) |

Host의 LLM이 이 규칙을 읽고 "질문에 답하기 전 `search_docs`를 호출해야
겠다"고 스스로 판단하는 구조다. 규칙의 핵심 내용(양쪽 파일 공통):

- 문서/코드 질문에는 **답변 전에 `search_docs`를 먼저 호출**한다.
- 검색 결과를 근거로 답하고, **참고한 파일 경로를 함께 표시**한다.
- 검색 결과에 없는 내용은 추측하지 않는다("모르면 모른다"고 답한다).
- `reindex` 실행은 반드시 사용자 승인을 먼저 받는다.

## MCP 호스트에 가져가야 할 파일들

새 PC(또는 다른 머신)에서 OpenCode/Cline 같은 Host 가 `cline-rag` 를 MCP
서버로 쓰려면, 이 저장소를 통째로 clone 하는 것이 원칙이다. Host 는
`rag_server.py` 하나만 실행하지만, 그 파일이 `rag_core.py` 에 의존하고
(`rag_core.py` 가 `PROJECT_DIR`, 즉 `src/` 의 부모 디렉터리를 기준으로
`config.json`/`docs/`/`rag_store_chroma/` 를 찾는다), 색인 없이는 검색
결과도 없기 때문에 파일 몇 개만 떼어가는 것은 권장하지 않는다.

### 저장소에서 통째로 가져와야 하는 것 (git clone)

| 항목 | 왜 필요한가 |
|---|---|
| `src/rag_server.py` | Host 가 자식 프로세스로 실행하는 MCP 서버 본체 |
| `src/rag_core.py` | `rag_server.py` 가 `import` 하는 검색 엔진(필수 의존) |
| `src/ingest.py` | `reindex` 도구가 내부적으로 자식 프로세스로 호출 |
| `config.json` | 임베딩 제공자·저장소 경로·청킹 설정(없어도 기본값으로 동작은 하지만, 커스텀했다면 필요) |
| `docs/` | 색인 대상 원본 문서 — 이게 있어야 검색할 내용이 생긴다 |
| `AGENTS.md` (OpenCode) / `clinerules-template.md` (Cline) | Host 가 "언제 `search_docs` 를 호출할지" 판단하는 행동 규칙 |
| `requirements.txt` | `rag_server.py` 실행에 필요한 Python 패키지 목록 |

### 새 머신에서 별도로 다시 만들어야 하는 것 (git에 없음)

| 항목 | 이유 | 만드는 방법 |
|---|---|---|
| `.venv/` | `.gitignore` 대상, 머신마다 파이썬 경로가 다름 | `setup.ps1` 이 생성 |
| `rag_store_chroma/` (색인된 벡터 저장소) | `.gitignore` 대상, 임베딩 결과물이라 용량이 크고 재생성 가능 | `python src\ingest.py --reset` |
| Host 쪽 MCP 등록 설정(`opencode.json`/`cline_mcp_settings.json`) | 머신 전용 절대경로(`.venv` 위치)가 들어가므로 저장소에 커밋 안 함 | `.\ask.ps1 --mcp-install [--mcp-target opencode]` |

> 즉 "가져가는 것"은 **저장소 전체**이고, "새로 만드는 것"은 **머신에 종속된
> 3가지**(가상환경, 색인 결과물, Host 등록 설정)뿐이다. 이 절차는
> **[GETTING_STARTED.md](GETTING_STARTED.md) 7단계 "다른 PC에서 다시
> 설치(이관)하기"** 에 실행 명령까지 그대로 정리되어 있다.

## 등록(연결) 방법 요약

Host마다 MCP 서버 등록 방식(설정 파일 스키마)이 다르다. `src/ask.py`의
`--mcp-target`이 이 차이를 흡수한다.

| Host | 설정 파일 | 스키마 | 등록 명령 |
|---|---|---|---|
| Cline | `~/.cline/data/settings/cline_mcp_settings.json` | `mcpServers.<name>.command` + `args`(배열) + `disabled` + `autoApprove` | `.\ask.ps1 --mcp-install` (기본값) |
| OpenCode | `~/.config/opencode/opencode.json` | `mcp.<name>.type` + `command`(실행파일+인자 한 배열) + `enabled` | `.\ask.ps1 --mcp-install --mcp-target opencode` |

두 파일 모두 **머신 전용 전역 경로**이며 이 저장소에는 커밋하지 않는다
(`.venv`의 절대 경로가 머신마다 다르기 때문).

## 관련 소스 파일 지도

| 파일 | 역할 |
|---|---|
| `src/rag_server.py` | MCP 서버 본체(stdio JSON-RPC, 도구 정의/디스패치) |
| `src/rag_core.py` | 검색 엔진(임베딩·Chroma·BM25·LangGraph 오케스트레이션) — MCP와 무관하게 독립적으로 재사용 가능 |
| `src/ingest.py` | 색인 CLI, `reindex` 도구가 자식 프로세스로 호출 |
| `src/ask.py` | MCP 없이 터미널에서 같은 검색 로직을 바로 쓰는 CLI + MCP 등록 관리(`--mcp-*`) |
| `AGENTS.md` / `clinerules-template.md` | Host가 로드하는 "언제 검색할지" 행동 규칙 |
| `config.json` | 임베딩 제공자/저장소/청킹 설정(Host와 무관, 서버 쪽 설정) |

## 한 줄 요약

**`cline-rag`는 RAG 파이프라인의 "검색(R)" 부분을 MCP 서버로 캡슐화한
것이고, OpenCode·Cline은 이 서버를 자식 프로세스로 실행해 MCP 프로토콜로
대화하는 Host이며, 실제 "생성(G)"은 Host의 LLM이 검색 결과를 컨텍스트로
받아 수행한다.**
