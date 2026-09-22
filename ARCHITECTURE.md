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
     │                                          ├─ Ollama: 질문 → 벡터
     │                                          ├─ Chroma: 벡터 유사도 검색
     │                                          └─ BM25: 키워드 검색(hybrid)
     │                                                        │
     │◄───────────────────────────────────────────────────────┤
     │  결과: docs/example_vacation_policy.md#chunk0 원문 발췌  │
     ▼
[Host의 LLM 이 이 발췌를 "증강된 컨텍스트"로 받아 최종 답변 생성]
  → "연차는 1년 차 15일, 3년 이상 근무 시 2년마다 1일 추가, 최대 25일..."
```

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
