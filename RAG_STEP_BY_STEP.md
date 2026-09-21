# Cline 에서 RAG 만들기 — Step by Step

Cline 에 **로컬 RAG(검색 증강 생성)** 를 잇는 전 과정입니다.
결과물은 `search_docs` 도구를 가진 MCP 서버이고, Cline 이 대화 중에 스스로 호출합니다.

> 빠르게 설치만 하고 싶다면 이 문서 대신 **[GETTING_STARTED.md](GETTING_STARTED.md)**
> (처음 사용자용 매뉴얼)를 먼저 보세요. 이 문서는 "왜 이렇게 만들었는지"까지
> 다루는 상세 가이드입니다.

---

## 0. 먼저 알아야 할 전제

| 항목 | 사실 |
|---|---|
| Cline 내장 벡터 검색 | **없음**. Continue 의 `@Codebase` 같은 내장 인덱스가 없다. |
| Cline 의 기본 코드 탐색 | `read_file` / `grep` / `list_files` **도구 기반 탐색** (벡터 아님) |
| 진짜 벡터 RAG 를 붙이는 방법 | **MCP 서버**로 검색기를 만들어 등록한다 |
| 정적 컨텍스트 주입 | `.clinerules/` 파일 (검색이 아니라 항상 포함되는 규칙) |
| 이 프로젝트의 구현 | **LangChain + LangGraph** (v2.0.0부터) → Chroma 벡터 저장소, `pip install` 필요 |

> 핵심: Cline 은 "RAG 를 직접 하는 에이전트"가 아니라 **RAG 도구를 호출하는 에이전트**입니다.
> 그래서 검색기를 MCP 서버로 노출하기만 하면 됩니다.

### 전체 구조

```
[원본 문서] -> src/ingest.py -> (LangChain 임베딩) -> rag_store_chroma/ (Chroma 벡터 저장소)
                                                            ^
                                                            | LangGraph 검색 그래프
[Cline] --MCP(stdio)--> src/rag_server.py ------------------+
   |
   +-- 필요할 때 search_docs 도구를 스스로 호출
```

---

## 1. 준비물 확인

```powershell
python --version          # 3.10+ (검증 환경: 3.13.5)
ollama --version          # 로컬 임베딩을 쓸 경우
cmake --version           # 테스트 팩을 쓸 경우 (검증 환경: 4.4.3)
```

런타임 의존성은 LangChain/LangGraph/Chroma 등입니다(`requirements.txt` 참고).
테스트에는 `pytest` 가 필요합니다.

---

## 2. 프로젝트 구조와 가상환경

```powershell
cd C:\path\to\cline_rag
```

### 2-1. 한 번에 설정 + 검증

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`setup.ps1` 이 하는 일: venv 생성 → pip 최신화 → `requirements.txt` →
`requirements-dev.txt` → 임베딩 모델 확인 → 색인 → MCP 스모크 검사 →
pytest → CMake/CTest.

CMake 단계를 건너려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -SkipCmake
```

### 2-2. 수동으로 하기

```powershell
python -m venv .venv                          # 가상환경 생성
.\.venv\Scripts\Activate.ps1                  # 활성화
python -m pip install --upgrade pip           # pip 최신화
python -m pip install -r requirements.txt     # 런타임 의존성 (LangChain/LangGraph/Chroma)
python -m pip install -r requirements-dev.txt # pytest

python --version                              # .venv 의 파이썬인지 확인
```

> **왜** 시스템 파이썬 대신 venv 인가?**
> 이 PC 는 `python` 이 Windows Store 셰임
> (`%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`)을 가리킵니다.
> 이걸 MCP `command` 로 쓰면 기동에 실패할 수 있습니다.
> `.venv\Scripts\python.exe` 는 실제 인터프리터의 **고정된 절대 경로**라 안전합니다.

### 2-3. 소스는 src/ 에 있습니다

```
cline_rag/
├── .venv/                     # 가상환경 (git 제외)
├── src/                       # 소스
│   ├── rag_core.py            # 임베딩 + SQLite 벡터 저장소 + 코사인 검색
│   ├── ingest.py              # 문서 -> 청크 -> 임베딩 -> 색인 CLI
│   └── rag_server.py          # MCP stdio 서버 (도구 3개)
├── tests/                     # pytest 테스트
│   ├── conftest.py            # 공용 픽스처 (외부 서비스 불필요)
│   ├── test_rag_core.py       # 코어 단위 테스트
│   └── test_mcp_server.py     # MCP 프로토콜/도구 테스트
├── docs/                      # 색인할 문서
├── CMakeLists.txt             # 테스트 패킹 유틸 (pytest -> CTest 래핑)
├── CMakePresets.json          # default / ninja / ci 프리셋
├── pytest.ini                 # pytest 설정
├── config.json                # 임베딩 제공자 / 저장소 / 청킹 설정
├── smoke_mcp.py               # 서버를 자식 프로세스로 띄우는 스모크 검사
├── setup.ps1                  # 원클릭 설정
├── requirements.txt           # 런타임 (필수 서드파티 없음)
├── requirements-dev.txt       # 테스트 (pytest)
├── requirements-optional.txt  # 선택 확장 (pypdf)
├── clinerules-template.md     # Cline 규칙 템플릿
└── rag_store_chroma/          # 색인 결과, Chroma 저장소 (git 제외)
```

**경로 규칙**: 소스는 `src/`, 데이터(`config.json`, `rag_store_chroma/`)는 프로젝트 루트에
둡니다. `rag_core.PROJECT_DIR` 이 기준을 결정하므로 실행 위치와 무관하게 동작합니다.

### 2-4. 의존성 기록

```powershell
python -m pip freeze > requirements.lock.txt   # 실제 설치 버전 고정(재현용)
```

| 파일 | 내용 |
|---|---|
| `requirements.txt` | 런타임 필수 — **없음** (표준 라이브러리만) |
| `requirements-dev.txt` | `pytest>=8.0` (테스트/CMake) |
| `requirements-optional.txt` | `numpy`(검색 가속), `pypdf`(PDF 색인) |

---

## 3. 임베딩 준비 (둘 중 하나 선택)

### 방법 A — 로컬(Ollama), 권장

```powershell
ollama pull nomic-embed-text
ollama list                      # nomic-embed-text 가 보이면 성공
```

`config.json` 을 로컬로 설정합니다.

```json
{ "embedding": { "provider": "ollama",
                 "ollama": { "apiBase": "http://127.0.0.1:11434",
                             "model": "nomic-embed-text" } } }
```

### 방법 B — OpenAI

```powershell
$env:OPENAI_API_KEY = "sk-..."   # 세션에만 적용
```

`config.json` 의 `provider` 를 `openai` 로 바꿉니다. 키는 **파일에 직접 쓰지 말고
환경 변수**로 넘기세요(MCP 등록 시 `env` 로 주입).

```json
{ "embedding": { "provider": "openai",
                 "openai": { "model": "text-embedding-3-small",
                             "apiKeyEnv": "OPENAI_API_KEY" } } }
```

> 주의: 한번 색인한 뒤에는 **임베딩 모델을 바꾸지 마세요.** 벡터 공간이 달라져
> 기존 색인과 비교할 수 없습니다. 바꾸면 `--reset` 으로 전체 재색인하세요.

---

## 4. 문서 넣기

`docs/` 폴더에 색인할 파일을 넣습니다. 기본 지원 확장자:
`txt, md, py, js, ts, json, yaml, sql, html, csv, ps1, sh` 등
(`rag_core.TEXT_SUFFIXES` 에서 수정 가능)

```powershell
copy ..\MCP_gateway\README.md .\docs\      # 예시: 기존 문서 복사
```

PDF/Word 를 넣으려면 별도 추출 단계가 필요합니다(12장 확장 참고).

---

## 5. 색인 실행

```powershell
python src\ingest.py                 # docs/ 전체 색인
python src\ingest.py --reset         # 비우고 새로 색인 (모델 바꿨을 때)
python src\ingest.py docs README.md  # 특정 경로만 색인
python src\ingest.py --prune         # 삭제된 파일의 청크 제거
python src\ingest.py --stats         # 현황만 보기
python src\ingest.py --list          # 색인된 파일 목록
```
- MCP 도구 `reindex` 로 Cline 안에서 바로 재색인할 수 있다.

정상 출력 예시:

```
임베딩 제공자 : ollama
저장소        : C:\...\cline_rag\rag_store_chroma
대상 파일     : 1개
청크 8개 임베딩 중...
  진행 8/8
색인 완료: 8개 청크 저장
  총 청크   : 8
  총 파일   : 1
  벡터 차원 : 768
```

여기서 오류가 나오면 10장 문제 해결을 먼저 보세요.

---

## 6. 검색 단독 테스트 (MCP 붙이기 전)

```powershell
$env:PYTHONPATH = "src"
python -c "import rag_core as c; [print(round(h['score'],4), h['source'].split('\\')[-1], '|', h['text'][:60].replace(chr(10),' ')) for h in c.semantic_search('청크 크기는 얼마가 좋아?', top_k=3)]"
```

`score` 가 0.5 이상이고 관련 문장이면 성공입니다.
이 단계를 건너뛰면 나중에 문제가 생겼을 때 **임베딩 문제인지 MCP 등록 문제인지**
구분할 수 없습니다.

---

## 7. Cline 에 MCP 서버 등록

### 7-1. 설정 파일 위치

| 사용 환경 | 경로 |
|---|---|
| VS Code 확장 | Cline 패널 → MCP Servers 아이콘 → Configure 탭 → **Configure MCP Servers** 버튼 |
| 이 PC 의 실제 파일 | `C:\Users\<you>\.cline\data\settings\cline_mcp_settings.json` |
| Cline CLI | `~/.cline/mcp.json` |

### 7-2. 등록 내용

`mcpServers` 아래에 항목을 추가합니다.

```json
{
  "mcpServers": {
    "cline-rag": {
      "command": "C:\\path\\to\\cline_rag\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\path\\to\\cline_rag\\src\\rag_server.py"
      ],
      "env": {
        "OPENAI_API_KEY": "sk-... (OpenAI 임베딩을 쓸 때만)"
      },
      "disabled": false,
      "autoApprove": ["search_docs", "list_indexed_sources", "index_status"]
    }
  }
}
```

**중요 포인트**

- `command` 는 **`.venv\Scripts\python.exe` 절대 경로**를 씁니다.
  시스템 `python` 은 Windows Store 셰임을 가리킬 수 있어 MCP 기동에 실패합니다.
- `args` 는 **`src\rag_server.py`** 입니다(소스가 src/ 에 있음).
- 경로 구분자는 **백슬래시 두 개(`\\`)** 여야 합니다(JSON 이스케이프).
- `autoApprove` 에 `search_docs` 를 넣으면 매번 승인 버튼을 누르지 않아도 됩니다.
  읽기 전용 도구만 넣고, 쓰기/삭제 도구는 넣지 마세요.
- 비밀 값은 `env` 로 주입합니다(JSON 에 평문 커밋 금지).
- `rag_server.py` 는 자기 파일 위치를 기준으로 동작하므로 MCP 의 작업 디렉터리와 무관합니다.

### 7-3. 연결 확인

1. Cline 패널에서 **MCP Servers** 아이콘을 엽니다.
2. `cline-rag` 가 초록색(연결됨)인지 봅니다.
3. 도구 목록에 `search_docs`, `list_indexed_sources`, `index_status` 가 보이는지 확인합니다.
4. `index_status` 를 한 번 직접 실행해 봅니다.

안 되면:
- `python smoke_mcp.py` 로 서버 자체를 먼저 검사합니다
- Cline 의 MCP 서버 출력 패널에서 stderr 로그를 봅니다
- 경로에 공백/한글이 있으면 따옴표 처리를 확인합니다

---

## 8. Cline 에서 실제로 사용하기

등록이 끝나면 Cline 채팅에서 이렇게 쓰면 됩니다.

```
docs/ 규칙에 맞춰 청크 크기를 정하려면 어떻게 해야 해? 저장소 근거로 답해줘.
```

Cline 은 내부적으로 `search_docs("청크 크기 권장")` 를 호출하고, 반환된 청크를
근거로 답합니다. 도구 호출은 채팅 로그에 표시되므로 **정말 검색을 했는지** 확인할 수 있습니다.

### 자동 호출을 유도하는 규칙 (`.clinerules`)

워크스페이스 루트에 `.clinerules` 폴더를 만들고 규칙 파일을 추가합니다.

`.clinerules/rag.md`
```markdown
# 문서 검색 규칙

- 이 워크스페이스의 문서/코드에 대해 질문받으면 답변 전에
  `search_docs` 도구를 먼저 호출한다.
- 검색 결과를 근거로 답하고, 사용한 파일 경로를 함께 밝힌다.
- 검색 결과가 비어 있으면 추측하지 말고 색인이 필요하다고 알린다.
- `ingest.py` 를 실행해야 할 때는 사용자에게 먼저 확인을 받는다.
```

> 이 저장소의 `clinerules-template.md` 를 그대로 복사해도 됩니다.
> `.clinerules` 는 **워크스페이스 루트**에 만들어야 적용됩니다.

---

## 9. 테스트 — pytest 와 CMake/CTest

이 프로젝트는 **CMake 를 컴파일이 아니라 테스트 패킹 유틸** 로 씁니다
(`LANGUAGES NONE`). CMake 가 격리된 `test-venv` 를 만들고 `pytest` 를 설치한 뒤,
pytest 실행을 **CTest 테스트로 감쌉니다(wrapping)**.

### 9-1. pytest 직접 실행

```powershell
python -m pytest tests -q               # 전체
python -m pytest tests -v               # 상세
python -m pytest tests/test_rag_core.py -v      # 코어 단위만
python -m pytest tests/test_mcp_server.py -v    # MCP 만
```

테스트는 **외부 서비스에 의존하지 않습니다.** `conftest.py` 가 임베딩을
결정적 가짜 함수로 바꾸므로 Ollama/OpenAI 없이 돕니다.

| 파일 | 검증 내용 |
|---|---|
| `tests/test_rag_core.py` | 설정 병합, 청킹(경계/겹침/예외), 코사인 유사도, 저장소 CRUD, 검색 순위·top_k·min_score·sources 필터 |
| `tests/test_mcp_server.py` | initialize/ping/notifications, tools/list 스키마, 3개 도구 실행, 오류 코드(-32601/-32602/-32700), 순서 보장 |

### 9-2. CMake + CTest (프리셋)

```powershell
cmake --preset default        # build/test-venv 생성 + pytest 설치 + 테스트 등록
ctest --preset default        # 전체 테스트 팩
ctest --preset unit           # 라벨 unit 만
ctest --preset mcp            # 라벨 mcp 만
```

### 9-3. CMake + CTest (프리셋 없이)

```powershell
cmake -S . -B build
ctest --test-dir build -C Debug --output-on-failure
ctest --test-dir build -C Debug --show-only      # 등록된 테스트 목록
ctest --test-dir build -C Debug -L mcp           # 라벨 필터
cmake --build build --config Debug --target test-pack   # 한 번에
```

### 9-4. 등록되는 CTest 테스트

| 이름 | 실행 내용 | 라벨 |
|---|---|---|
| `rag.unit` | `pytest tests/test_rag_core.py -v` | `rag;unit` |
| `rag.mcp` | `pytest tests/test_mcp_server.py -v` | `rag;mcp;protocol` |
| `rag.smoke` | `smoke_mcp.py` (서버를 자식 프로세스로 띄워 핸드셰이크) | `rag;smoke` |

`PYTHONPATH=src` 가 각 테스트의 `ENVIRONMENT` 로 주입되므로
`add_test` 가 `src/` 모듈을 항상 임포트할 수 있습니다.

### 9-5. CMake 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `CLINE_RAG_SETUP_TEST_ENV` | `ON` | `build/test-venv` 생성 + 테스트 의존성 설치 |
| `BUILD_TESTING` | `ON` | `include(CTest)` 가 정의 |

이미 만든 `.venv` 를 재사용하면 configure 가 빨라집니다.

```powershell
cmake -S . -B build-ninja -G Ninja -DCMAKE_BUILD_TYPE=Debug `
  -DCLINE_RAG_SETUP_TEST_ENV=OFF `
  -DPython3_EXECUTABLE="$PWD\.venv\Scripts\python.exe"
ctest --test-dir build-ninja --output-on-failure
```

### 9-6. 왜 CTest 로 감싸는가

| 이점 | 설명 |
|---|---|
| 단일 진입점 | `ctest` 하나로 전체 팩 실행, 종료 코드로 CI 연동 |
| 선택 실행 | 라벨로 `-L mcp` 처럼 골라 실행 |
| 환경 격리 | 각 테스트에 `PYTHONPATH`/`TIMEOUT` 을 선언적으로 지정 |
| 타임아웃 | 멈춘 테스트가 전체를 막지 않음 |
| 격리된 venv | 프로젝트 `.venv` 를 오염시키지 않고 테스트 의존성 관리 |

---

## 10. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 서버가 빨간색(연결 실패) | `command` 경로 오류 | `.venv\Scripts\python.exe` 절대 경로로 지정. 시스템 `python` 이 Windows Store 셰임이면 실패 |
| 도구가 안 보임 | 서버 미기동 | `python smoke_mcp.py` 로 확인. stderr 는 터미널에 그대로 보임 |
| 검색 결과 0건 | 색인 안 됨 | `python src\ingest.py --stats` 로 확인 후 `python src\ingest.py` |
| `색인 저장소가 없습니다` | 경로 불일치 | `config.json` 의 `store.path` 는 프로젝트 루트 기준 상대 경로 |
| 임베딩 차원 불일치 | 인/검색 모델이 다름 | `python src\ingest.py --reset` 로 전체 재색인 |
| Ollama 연결 실패 | 서버 미실행 | `ollama serve` 실행, `ollama list` 로 모델 확인 |
| 검색이 느림 | 순수 파이썬 코사인 | 청크가 수만 개 이상이면 12장 확장 참고 |
| `ModuleNotFoundError: rag_core` | PYTHONPATH 미설정 | `$env:PYTHONPATH = "src"` 또는 프로젝트 루트에서 `python src\ingest.py` 로 실행 |
| `ctest` 가 "No tests were found" | configure 미실행 또는 BUILD_TESTING=OFF | `cmake --preset default` 먼저 실행 |
| CMake configure 실패 | pip 설치 실패/네트워크 | `build/CMakeFiles/CMakeConfigureLog.yaml` 확인. 기존 venv 재사용(`-DCLINE_RAG_SETUP_TEST_ENV=OFF`) |

### 디버깅 명령

```powershell
# 1) 서버를 자식 프로세스로 띄워 핸드셰이크 검사 (pytest 불필요)
python smoke_mcp.py

# 2) 임베딩만 따로 확인
$env:PYTHONPATH = "src"
python -c "import rag_core as c; cfg = c.load_config(); e = c.build_embeddings(cfg); print(len(e.embed_query('test')))"

# 3) 색인 현황
python src\ingest.py --stats

# 4) 테스트 팩
python -m pytest tests -q
ctest --preset default
```

### PowerShell 5.1 `.ps1` 파싱 오류

이 PC 의 `powershell.exe` 는 **5.1** 이고, BOM 없는 UTF-8 파일을 ANSI(cp949)로
읽습니다. 한국어가 들어간 `.ps1` 은 문법 오류로 보일 수 있습니다.
이 저장소의 `setup.ps1` 은 **영문 메시지로만** 작성해 이 문제를 피했습니다.
직접 만든 스크립트에 한국어를 넣어야 하면 BOM 을 추가하세요.

```powershell
$c = [System.IO.File]::ReadAllText('script.ps1', [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText((Join-Path (Get-Location) 'script.ps1'), $c, [System.Text.UTF8Encoding]::new($true))
```

---

## 11. 운영: 문서가 바뀌면

색인은 **자동으로 갱신되지 않습니다.** 문서를 추가/수정하면 다시 돌려야 합니다.

```powershell
python src\ingest.py            # 증분 갱신 (은 파일은 덮어씀, 빠름)
python src\ingest.py --prune    # 삭제된 파일의 청크 제거
```

`reset` 없이 그냥 돌리면 `(source, chunk_index)` 기준으로 덮어쓰므로 빠릅니다.

### Git 훅으로 자동화 (선택)

`.git/hooks/post-commit`:

```bash
#!/bin/sh
python "C:/path/to/cline_rag/src/ingest.py" >/dev/null 2>&1 &
```

생성물은 커밋하지 마세요(`.gitignore` 에 이미 포함):

```gitignore
.venv/
build/
build-*/
rag_store.sqlite3
rag_store_chroma/
__pycache__/
```

---

## 12. 확장 아이디어

| 목표 | 방법 |
|---|---|
| PDF/Word 색인 | `pypdf` / `python-docx` 로 텍스트 추출 후 `build_chunk_rows` 에 넘김 |
| 검색 속도 | `numpy` 로 벡터 행렬화, 또는 `sqlite-vec` / `chromadb` / `faiss` 도입 |
| 정확도 향상 | BM25(키워드) + 벡터(의미) **하이브리드 검색** 후 RRF 로 병합 | — **v1.1.0 구현**
| 순위 개선 | 상위 20건 검색 후 LLM 으로 재정렬(rerank) |
| 파일 필터 | `search_docs` 에 `sources` 인자 추가 (코어의 `search()` 는 이미 지원) | — **v1.1.0 구현**
| 자동 재색인 | MCP 도구에 `reindex` 추가 (쓰기 도구이므로 `autoApprove` 에는 넣지 말 것) | — **v1.1.0 구현**
| 다중 프로젝트 | `config.json` 을 프로젝트별로 두고 서버를 여러 개 등록 |

> 확장 시 주의: `autoApprove` 에는 **읽기 전용 도구만** 넣으세요.
> 색인/삭제 같은 쓰기 도구를 자동 승인하면 에이전트가 저장소를 임의로 바꿀 수 있습니다.

---

## 13. Git / GitHub 워크플로

### 13-1. 저장소 형태

`cline_rag` 는 **독립 저장소** 입니다. 상위 `~/.openclaw/workspace` 에도 git 저장소가
있으므로 주의가 필요합니다.

| 항목 | 값 |
|---|---|
| 저장소 | `populous/cline-rag` (public) |
| 기본 브랜치 | `main` |
| remote | `origin` = `https://github.com/populous/cline-rag.git` |
| 버전 단일 출처 | `src/rag_server.py` 의 `SERVER_VERSION` |

> **중요**: 상위 workspace 저장소에서는 `cline_rag/` 를 **`git add` 하지 마세요.**
> 중첩 저장소가 gitlink 로 들어가 오염됩니다. 막으려면 상위 `.gitignore` 에
> `cline_rag/` 한 줄을 추가하세요.

### 13-2. 최초 설정 (이미 완료된 절차)

```powershell
cd C:\path\to\cline_rag

# 1) .gitattributes 를 먼저 (줄바꿈 churn 방지) — setup.ps1 은 CRLF 유지
#    * text=auto eol=lf  /  *.ps1 text eol=crlf  /  *.sqlite3 binary

# 2) main 브랜치로 초기화 (전역 defaultBranch 미설정 대비)
git init -b main

# 3) 커밋 신원 (전역 미설정이므로 로 지정)
git config user.name  "populous"
git config user.email "populous@empas.com"

# 4) 스테이징 전 확인 — .venv/build/rag_store_chroma 가 보이면 중단
git add -A
git status --short
git check-ignore -v .venv build rag_store_chroma

# 5) 초기 커밋
git commit -m "feat: add local RAG MCP server for Cline"

# 6) GitHub 저장소 생성 + 푸시 + origin 자동 설정
gh repo create cline-rag --public --source=. --remote=origin `
  --description "Local RAG (retrieval-augmented generation) MCP server for Cline" `
  --push
```

### 13-3. 일상 개발 흐름

```powershell
git switch main; git pull --ff-only      # 1) main 최신화
git switch -c fix/chunk-boundary         # 2) 단기 브랜치

# 3) 수정 + 로컬 검증
python -m pytest tests -q
python smoke_mcp.py
ctest --preset default

# 4) 커밋 (Conventional Commits)
git add -A
git commit -m "fix: correct chunk boundary at document end"

# 5) 푸시 + PR
git push -u origin fix/chunk-boundary
gh pr create --base main --fill

# 6) CI 확인 (초록이 될 때까지)
gh pr checks --watch

# 7) 병합 + 정리
gh pr merge --squash --delete-branch
git switch main; git pull --ff-only; git fetch --prune
```

브랜치 이름: `feat/…` `fix/…` `docs/…` `test/…` `chore/…` `release/…`

### 13-4. Merge 정책

| 상황 | 명령 | 이유 |
|---|---|---|
| 기능/수정 PR (기본) | `gh pr merge --squash --delete-branch` | main 히스토리를 릴리스 단위로 깔끔하게 |
| 릴리스 브랜치 | `gh pr merge --merge --delete-branch` | 릴리스 경계를 merge 커밋으로 명시 |
| main 최신화 | `git pull --ff-only` | 불필요한 merge 커밋 방지 |
| 충돌 해결 | 브랜치에서 `git rebase main` 후 `git push --force-with-lease` | `--force` 대신 lease 사용 |

### 13-5. 릴리스 절차 (SemVer)

| 버전 | 올리는 시점 |
|---|---|
| MAJOR | MCP 도구 스키마/저장소 스키마 **호환성 파괴** (예: `search_docs` 인자 제거) |
| MINOR | 하위호환 **기능 추가** (예: 하이브리드 검색, `sources` 필터) |
| PATCH | 하위호환 **버그 수정** |

```powershell
# 1) 릴리스 브랜치
git switch -c release/v1.1.0

# 2) 두 곳만 갱신
#    - src/rag_server.py : SERVER_VERSION = "1.1.0"
#    - CHANGELOG.md      : ## [1.1.0] - YYYY-MM-DD

# 3) 최종 검증
python -m pytest tests -q
ctest --preset default

# 4) 릴리스 커밋 -> PR -> 병합(--merge 로 경계 표시)
git add src/rag_server.py CHANGELOG.md
git commit -m "chore(release): v1.1.0"
git push -u origin release/v1.1.0
gh pr create --base main --title "chore(release): v1.1.0" --fill
gh pr merge --merge --delete-branch

# 5) main 에서 태그 + 푸시
git switch main; git pull --ff-only
gh run list --branch main --limit 3        # CI 초록 확인
git tag -a v1.1.0 -m "v1.1.0"
git push origin main --follow-tags

# 6) GitHub Release
gh release create v1.1.0 --title "v1.1.0" --generate-notes
```

### 13-6. 핫픽스 릴리스 (긴급 수정)

```powershell
git switch -c fix/chunk-boundary v1.0.0     # 태그에서 분기
# 수정 + 테스트
git commit -m "fix: correct chunk boundary at document end"
git switch main
git merge --no-ff fix/chunk-boundary
# SERVER_VERSION -> 1.0.1, CHANGELOG 갱신
git tag -a v1.0.1 -m "v1.0.1"
git push origin main --follow-tags
gh release create v1.0.1 --generate-notes
```

### 13-7. 브랜치 보호 (선택)

1인 개발이므로 **PR 은 필수, 승인은 불필요** 로 두는 것이 실용적입니다.

```powershell
gh api -X PUT repos/populous/cline-rag/branches/main/protection `
  -F "required_status_checks[strict]=true" `
  -F "required_status_checks[contexts][]=test (windows-latest)" `
  -F "enforce_admins=false" `
  -F "required_pull_request_reviews[required_approving_review_count]=0" `
  -F "restrictions="
```

### 13-8. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `UnicodeEncodeError` (CI) | 러너 콘솔이 cp1252 | 해당 스크립트에서 stdout/stderr 를 UTF-8 로 `reconfigure` (이 저장소는 적용됨) |
| `Please tell me who you are` | 커밋 신원 미설정 | `git config user.name/user.email` (로컬) |
| `src refspec main does not match any` | 커밋 전 푸시 | 먼저 커밋 |
| `.venv` 가 커밋됨 | `.gitignore` 누락/staged | `git rm -r --cached .venv` 후 재커밋 |
| CRLF 경고 폭주 | `.gitattributes` 없음 | 첫 커밋 **전**에 추가. 이미 늦었으면 `git add --renormalize .` |
| `Test not available without configuration` | VS 다중 구성 제너레이터 | `ctest -C Debug` 또는 `ctest --preset default` |
| PR CI 가 계속 실패 | 로컬과 환경 차이 | `gh run view <id> --log-failed` 로 실제 오류 확인 |
| 잘못 푸시함 | 되돌리기 필요 | `git push --force-with-lease`, 저장소 삭제는 `gh repo delete populous/cline-rag --yes` |

---

## 부록 A. 이 저장소의 검증 결과 (2026-09-20)

| 항목 | 결과 |
|---|---|
| Python (프로젝트 .venv) | 3.14.7 |
| CMake / CTest | 4.4.3 / 4.4.3 (제너레이터: Visual Studio 18 2026, x64) |
| 런타임 서드파티 의존성 | **0개** (`pip list` → pip 만 / AST 분석 THIRDPARTY=[]) |
| 테스트 의존성 | `pytest 9.1.1` (+ pluggy, iniconfig, packaging, pygments, colorama) |
| pytest | **49 passed** (`python -m pytest tests -q`) |
| CMake configure | **exit=0** (isolated test-venv 생성 + pytest 설치) |
| ctest 전체 | **3/3 passed, exit=0** (rag.unit 0.99s, rag.mcp 0.72s, rag.smoke 2.09s) |
| 라벨 필터 | `ctest -L unit` → 1/1 passed |
| test-pack 타깃 | `cmake --build build --config Debug --target test-pack` → **exit=0** |
| 임베딩 | Ollama `nomic-embed-text`, **768차원** |
| 색인 | 5청크 / 2파일 / 768차원 |
| MCP 등록 | `cline_rag\.venv\Scripts\python.exe` + `src\rag_server.py` |
| Git 저장소 | `populous/cline-rag` (public, 기본 브랜치 `main`) |
| 초기 커밋 | `a877371` feat: add local RAG MCP server for Cline (25 files, 3006 lines) |
| 첫 PR | #1 fix: force UTF-8 stdout (squash merge → `7949010`), CI 33s **pass** |
| 릴리스 | `v1.0.0` (태그 + GitHub Release) |
| CI | GitHub Actions `CI` / windows-latest / Python 3.12 / pytest 49 + smoke + CTest 3 |
| Release 1.1.0 | hybrid/keyword/sources + reindex MCP tool |

## 부록 B. 한눈에 보는 명령 요약

```powershell
cd C:\path\to\cline_rag

# 최초 1회 (venv + 의존성 + 색인 + pytest + CMake/CTest)
powershell -ExecutionPolicy Bypass -File .\setup.ps1

# 또는 수동으로
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
ollama pull nomic-embed-text

# 평소 사용
python src\ingest.py --reset     # 색인
python smoke_mcp.py              # MCP 스모크
python -m pytest tests -q        # pytest

# 테스트 팩 (CMake / CTest)
cmake --preset default
ctest --preset default
ctest --preset unit
ctest --preset mcp
cmake --build build --config Debug --target test-pack
```

### 의존성 관련 명령

```powershell
python -m pip list                                    # 설치된 패키지
python -m pip freeze > requirements.lock.txt          # 버전 고정(재현용)
python -m pip install -r requirements-dev.txt         # pytest
python -m pip install -r requirements-optional.txt    # numpy, pypdf (필요할 때만)
```

### CMake 관련 파일

| 파일 | 역할 |
|---|---|
| `CMakeLists.txt` | 테스트 팩 정의 (LANGUAGES NONE, CTest 등록, test-pack 타깃) |
| `CMakePresets.json` | `default`(VS 18 2026) / `ninja` / `ci` configure·build·test 프리셋 |
| `pytest.ini` | `testpaths`, `pythonpath = src tests`, `addopts` |
| `requirements-dev.txt` | `pytest>=8.0` (CMake 가 자동 설치) |
