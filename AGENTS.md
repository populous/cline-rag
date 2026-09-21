# cline-rag 문서 검색 규칙

이 워크스페이스에는 `cline-rag` MCP 서버(OpenCode 등록)가 연결되어 있다.

## 답변 전에 검색한다

- 이 프로젝트의 문서나 코드 내용을 묻는 질문에는 **답변 전에 `search_docs` 도구를 먼저 호출**한다.
- 질문을 그대로 넣지 말고 핵심 키워드 위주로 짧게 바꿔 검색한다.
- 결과가 부족하면 `top_k` 를 올려 다시 검색한다.

## 근거를 밝힌다

- 검색으로 얻은 내용을 근거로 답하고, 사용한 파일 경로를 함께 표시한다.
- 검색 결과에 없는 내용은 추측하지 않는다. 모르면 모른다고 답한다.
- 답변 마지막에 참고한 파일 목록을 정리한다.

## 검색 모드를 고른다

`search_docs` 의 `mode` 로 검색 방식을 고른다.

| 상황 | mode |
|---|---|
| 일반적인 질문 | `hybrid` (기본) |
| 표현이 달라도 의미로 찾아야 할 때 | `vector` |
| 함수명·에러코드·고유명사처럼 정확한 용어 | `keyword` (임베딩 호출 없이 빠름) |

- 특정 문서만 보고 싶으면 `sources` 에 색인된 파일 경로를 넣는다.
- `hybrid`/`keyword` 결과의 점수는 RRF 순위 점수다. 코사인 임계값이 필요하면
  `mode="vector"` 와 `min_score` 를 함께 쓴다.

## 색인 상태를 확인한다

- 검색 결과가 비어 있으면 `index_status` 로 색인 여부를 확인한다.
- 색인이 비어 있으면 `reindex` 실행이 필요하다고 사용자에게 알린다.
- **`reindex` 실행이나 색인 초기화는 반드시 사용자 승인을 먼저 받는다.**

## 하지 말아야 할 것

- `rag_store_chroma/` 를 직접 수정하지 않는다.
- `search_docs` 를 호출하지 않고 문서 내용을 지어내지 않는다.
- 임베딩 모델이나 `config.json` 을 임의로 바꾸지 않는다(바꾸면 전체 재색인 필요).

## 자주 쓰는 명령

```powershell
# 색인
.\.venv\Scripts\python.exe src\ingest.py --stats   # 현황
.\.venv\Scripts\python.exe src\ingest.py --list    # 색인된 파일 목록
.\.venv\Scripts\python.exe src\ingest.py --reset   # 전체 재색인

# 질의 (터미널에서 바로)
.\ask.ps1 "질문"
.\ask.ps1 "질문" --mode vector --top-k 5
.\ask.ps1 "질문" --json

# 테스트
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe smoke_mcp.py            # MCP 서버 스모크 테스트

# CMake/CTest (격리 테스트 환경)
cmake -S . -B build
ctest --test-dir build -C Debug --output-on-failure
```

## 저장소 구조

- `src/` — RAG 코어(`rag_core.py`), MCP 서버(`rag_server.py`), CLI(`ask.py`, `ingest.py`)
- `tests/` — pytest 테스트
- `docs/` — 색인 대상 문서
- `rag_store_chroma/` — Chroma 벡터 저장소(직접 수정 금지, git 제외)
- `config.json` — 임베딩/저장소/청킹 설정
- `AGENTS.md` — 이 규칙 파일(OpenCode가 자동 로드)
- MCP 등록은 `~/.config/opencode/opencode.json`(전역, 머신 전용 절대경로)에 저장되며
  저장소에는 커밋하지 않는다.
