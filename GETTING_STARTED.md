# 처음 사용자용 매뉴얼 (Getting Started)

`cline-rag`를 **한 번도 써 본 적 없는 사람**이 처음부터 끝까지 따라 할 수 있는
가장 빠른 경로입니다. "왜 이렇게 하는지"보다 "무엇을, 어떤 순서로" 하는지에
집중합니다. 배경 지식이나 전체 아키텍처가 궁금하면 **[RAG_STEP_BY_STEP.md](RAG_STEP_BY_STEP.md)**
를 참고하세요. 명령어 요약은 **[README.md](README.md)** 에 있습니다.

---

## 이 프로젝트가 하는 일 (한 문단 요약)

`cline-rag`는 여러분의 로컬 문서(`docs/` 폴더)를 미리 읽어서 검색 가능한 형태로
저장해두고, [Cline](https://cline.bot) 이 대화 중에 "이 질문에 답하려면 문서를
찾아봐야겠다" 싶을 때 스스로 호출하는 **MCP 서버**입니다. 여러분이 직접 검색
버튼을 누르는 게 아니라, Cline 이 필요할 때 알아서 씁니다.

---

## 0단계 — 준비물 체크리스트

시작하기 전에 아래 4가지가 있는지 확인하세요.

- [ ] **Windows PC** (이 가이드는 PowerShell 기준입니다)
- [ ] **Python 3.10 이상** — 설치 확인: `python --version`
- [ ] **[Ollama](https://ollama.com/download)** — 로컬 임베딩 모델을 돌리는 프로그램
      (인터넷에 API 키를 보내지 않고 내 PC 에서 임베딩을 계산합니다)
- [ ] **[Cline](https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev)** —
      VS Code 확장. 이미 설치되어 있다고 가정합니다.

Ollama 를 처음 설치했다면, 설치 후 한 번 실행해서 백그라운드로 떠 있는지
확인하세요(트레이 아이콘 또는 `ollama --version` 이 응답하면 정상).

---

## 1단계 — 프로젝트 내려받기

이미 저장소를 갖고 있다면 이 단계는 건너뛰세요.

```powershell
git clone https://github.com/populous/cline-rag.git
cd cline-rag
```

---

## 2단계 — 원클릭 설정 스크립트 실행

`cline-rag` 폴더 안에서 아래 한 줄만 실행하면 됩니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

이 스크립트가 순서대로 해 주는 일:

1. 가상환경(`.venv`) 생성
2. `pip` 최신화
3. 런타임 의존성 설치 (LangChain, LangGraph, Chroma 등 — 처음엔 1~2분 걸릴 수 있습니다)
4. 테스트 의존성(`pytest`) 설치
5. 임베딩 모델(`nomic-embed-text`) 이 없으면 Ollama 로 자동 다운로드
6. `docs/` 폴더 문서를 색인(Chroma 벡터 저장소 생성)
7. MCP 서버 스모크 테스트
8. 전체 pytest 실행
9. CMake/CTest 테스트 팩 실행

**모두 정상이면 마지막에 다음과 같은 메시지가 나옵니다.**

```
Setup complete.
Register this in your Cline MCP settings:
  command : C:\...\cline-rag\.venv\Scripts\python.exe
  args    : C:\...\cline-rag\src\rag_server.py
```

이 두 줄(`command`, `args`)은 **4단계(선택, Cline 채팅 연동)**에서 필요하니
기억해 두세요. 지금 당장은 필요 없습니다 — 바로 다음 단계에서 터미널로 질문할
수 있습니다.

> CMake 가 없거나 건너뛰고 싶다면:
> `powershell -ExecutionPolicy Bypass -File .\setup.ps1 -SkipCmake`

### 문제가 생겼다면?

| 증상 | 원인/해결 |
|---|---|
| `python` 명령을 찾을 수 없음 | Python 을 설치하고 PowerShell을 새로 열어보세요 |
| `ollama pull` 단계에서 멈춤/실패 | Ollama 앱이 실행 중인지 확인, 인터넷 연결 확인 |
| `requirements.txt install failed` | 인터넷 연결 확인, 방화벽/사내망이면 pip 미러 설정 필요할 수 있음 |
| 스크립트 자체가 안 실행됨 (`실행 정책` 오류) | `-ExecutionPolicy Bypass` 옵션을 빠뜻리지 않았는지 확인 |

---

## 3단계 — 지금 바로 질문해보기 (가장 빠른 방법)

VS Code 나 Cline 을 켜지 않고도, **터미널에서 바로** 질문하고 답을 볼 수
있습니다. 이게 가장 확실하고 가장 빠른 확인 방법입니다.

```powershell
cd C:\path\to\cline-rag
.\ask.ps1 "청크 크기는 얼마가 적당한가?"
```

`Enter` 를 누르면 **화면에 즉시** 검색 결과가 출력됩니다. 가상환경을
활성화하거나 `.venv` 경로를 직접 입력할 필요가 없습니다 — `ask.ps1` 이 항상
이 프로젝트의 `.venv` 파이썬을 자동으로 찾아서 실행해 줍니다
(cmd.exe 를 쓰신다면 `ask.cmd "질문"` 도 동일하게 동작합니다).

**실행 결과 예시:**

```
'청크 크기는 얼마가 적당한가?' [hybrid] 검색 결과 3건

[1] score=0.032787 | docs\sample.md#chunk1
## 4. 청크 크기 설계

청크가 너무 작으면 문맥이 부족하고, 너무 크면 검색 정밀도가 떨어진다.
일반적으로 500~1000자, 겹침은 청크 크기의 10~20% 를 권장한다.
이 프로젝트의 기본값은 size 800, overlap 120 이다.
...
```

이렇게 결과가 나오면 색인/검색이 정상 동작하는 것입니다. `ask.ps1` 자세한
옵션(`--top-k`, `--mode`, `--json` 등)은 6단계에서 다룹니다.

> **MCP/서버 기동 자체를 확인하고 싶다면**(예: Cline 연동 전 사전 점검):
> ```powershell
> .\.venv\Scripts\python.exe smoke_mcp.py
> ```
> `모든 검사 통과` 가 나오면 MCP 서버도 정상입니다.

---

## 4단계 — 선택: Cline 채팅에서도 쓰고 싶다면 (MCP 서버 등록)

`ask.ps1` 로 터미널에서 질문하는 것만으로도 충분하다면 이 단계는 건너뛰어도
됩니다. **Cline 과 대화하는 중에 Cline 이 스스로 문서를 검색하게** 하려면
MCP 서버로 등록하세요.

1. VS Code 에서 Cline 확장을 엽니다.
2. Cline 설정에서 **MCP Servers** 항목을 찾아 설정 파일을 엽니다. 보통 경로는:
   ```
   C:\Users\<사용자이름>\.cline\data\settings\cline_mcp_settings.json
   ```
3. 아래 내용을 채워 넣습니다(경로는 2단계에서 나온 값으로 바꾸세요).

```json
{
  "mcpServers": {
    "cline-rag": {
      "command": "C:\\path\\to\\cline-rag\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\cline-rag\\src\\rag_server.py"],
      "env": {},
      "disabled": false,
      "autoApprove": ["search_docs", "list_indexed_sources", "index_status"]
    }
  }
}
```

> ⚠️ **주의**: `command` 에는 시스템 `python` 이 아니라 반드시
> `.venv\Scripts\python.exe` 의 **전체 경로**를 넣어야 합니다. 그렇지 않으면
> MCP 서버가 켜지지 않을 수 있습니다.
>
> `reindex` 는 문서를 다시 쓰는 도구라서 `autoApprove` 목록에 **넣지 않습니다**
> (Cline 이 실행 전에 항상 여러분에게 승인을 요청하게 됩니다).

4. 설정 파일을 저장하면 Cline 이 자동으로 서버를 인식합니다. Cline 의 MCP
   서버 목록에서 `cline-rag` 가 초록불(연결됨)로 보이면 성공입니다.
5. Cline 채팅창에서 이렇게 확인해 보세요:
   > "search_docs 로 '청크 크기'에 대해 검색해줘"
   Cline 이 `search_docs` 도구를 스스로 호출하고 검색 결과를 바탕으로
   답하면 성공입니다. 결과는 방금 3단계에서 터미널로 본 것과 동일합니다
   (내부적으로 완전히 같은 코드 경로를 씁니다).

---

## 5단계 — 내 문서 추가하기

1. `docs/` 폴더에 원하는 문서(`.md`, `.txt`, `.py` 등)를 넣습니다.
2. 색인을 다시 돌립니다:

```powershell
.\.venv\Scripts\python.exe src\ingest.py
```

(전체를 완전히 새로 색인하려면 `--reset` 을 붙이세요: `python src\ingest.py --reset`)

3. 색인이 잘 됐는지 확인:

```powershell
.\.venv\Scripts\python.exe src\ingest.py --list    # 색인된 파일 목록
.\.venv\Scripts\python.exe src\ingest.py --stats   # 청크/파일 수 통계
```

또는 Cline 채팅에서 바로 "reindex 도구로 문서를 다시 색인해줘"라고 요청해도 됩니다
(이때는 승인 창이 뜨는 게 정상입니다).

---

## 6단계 — 실전 예시: 문서 1건을 등록해서 질의응답까지 해보기

앞 단계들이 "명령어를 어떻게 치는지"였다면, 이번엔 **문서 하나를 실제로 넣고
질문해서 답을 받는 전체 과정**을 그대로 따라 해봅니다. 아래 결과는 실제로
이 프로젝트에서 실행해서 얻은 출력입니다(여러분 PC 에서도 동일하게 나옵니다).

### 6-1. 예시 문서 준비

`docs/example_vacation_policy.md` 파일을 만들고 아래 내용을 넣습니다
(회사 실제 정책이 아니라 테스트용 가상 문서입니다).

```markdown
# 사내 휴가 신청 정책 (예시 문서)

## 1. 연차 휴가

- 입사 1년 차부터 매년 15일의 연차가 발생한다.
- 3년 이상 근무 시 2년마다 1일씩 추가되며, 최대 25일까지 늘어난다.
- 연차는 반차(0.5일) 단위로도 신청할 수 있다.

## 2. 신청 절차

1. 사내 인트라넷의 "휴가 신청" 메뉴에서 날짜와 사유를 입력한다.
2. 팀장 승인을 받으면 자동으로 캘린더에 반영된다.
3. 휴가 시작일 최소 3일 전까지 신청해야 한다.

## 3. 병가와 경조휴가

- 병가는 연 10일까지 별도로 부여되며, 3일 이상 사용 시 진단서가 필요하다.
- 경조휴가(결혼, 출산, 상조 등)는 사유별로 3~10일이 부여되고 연차에서 차감되지 않는다.
```

> 실제 예시 파일은 이 저장소의 `docs/example_vacation_policy.md` 에 이미 들어
> 있으니, 직접 만들지 않고 그대로 색인해서 따라 해봐도 됩니다.

### 6-2. 색인 등록 (Register)

```powershell
.\.venv\Scripts\python.exe src\ingest.py
```

**실제 실행 결과**:

```
임베딩 제공자 : ollama
저장소        : C:\...\cline-rag\rag_store_chroma
대상 파일     : 2개
청크 3개 임베딩/색인 중...

  진행 3/3
색인 완료: 3개 청크 저장
  총 청크        : 3
  총 파일        : 2
  임베딩 제공자  : OllamaEmbeddings
```

`docs/` 안의 두 파일(`sample.md`, `example_vacation_policy.md`)이 총 3개
청크로 나뉘어 Chroma 저장소(`rag_store_chroma/`)에 저장됩니다. 이 과정에서
Ollama 가 각 청크를 벡터(숫자 배열)로 변환합니다.

### 6-3. 색인 확인 (Verify)

```powershell
.\.venv\Scripts\python.exe src\ingest.py --list
```

```
1  C:\...\cline-rag\docs\example_vacation_policy.md
2  C:\...\cline-rag\docs\sample.md
```

앞의 숫자가 그 파일의 청크 수입니다. `example_vacation_policy.md` 는 짧아서
1개 청크, `sample.md` 는 좀 더 길어서 2개 청크로 나뉘었습니다.

### 6-4. 질의응답 (Query)

이제 방금 등록한 문서에만 있는 내용을 질문해봅니다. Cline 채팅창에 아래처럼
입력하면 Cline 이 `search_docs` 도구를 스스로 호출합니다.

> "연차는 반차 단위로도 신청할 수 있니?"

**Cline을 켜지 않고 터미널에서 바로 확인하고 싶다면 `ask.ps1` 을 쓰세요.**
파이프나 리다이렉션, MCP/JSON-RPC 를 전혀 몰라도 됩니다. 가상환경을
활성화하지 않아도, `python` 이 시스템 파이썬을 가리켜도 상관없습니다 —
`ask.ps1` 이 항상 `.venv` 의 파이썬을 자동으로 찾아서 실행해줍니다:

```powershell
.\ask.ps1 "연차는 반차 단위로도 신청할 수 있니?"
```

> ⚠️ **`.\.venv\Scripts\python.exe src\ask.py "..."` 처럼 직접 `.venv` 경로를
> 입력하지 않고, 그냥 `python src\ask.py "..."` 라고만 치면 시스템 파이썬이
> 실행되어 `ModuleNotFoundError: No module named 'langchain_community'`
> 오류가 납니다. 이 문제를 원천적으로 피하려고 만든 것이 `ask.ps1` 입니다.
> (cmd.exe 사용자는 `ask.cmd "질문"` 도 동일하게 동작합니다.)

**실제 실행 결과**:

```
'연차는 반차 단위로도 신청할 수 있니?' [hybrid] 검색 결과 3건

[1] score=0.032787 | docs\example_vacation_policy.md#chunk0
# 사내 휴가 신청 정책 (예시 문서)
...
## 1. 연차 휴가

- 입사 1년 차부터 매년 15일의 연차가 발생한다.
- 3년 이상 근무 시 2년마다 1일씩 추가되며, 최대 25일까지 늘어난다.
- 연차는 반차(0.5일) 단위로도 신청할 수 있다.

## 2. 신청 절차
...
```

Cline 은 이 검색 결과(문서 원문 발췌)를 근거로 삼아 "네, 연차는 반차(0.5일)
단위로도 신청할 수 있습니다."처럼 **문서에 실제로 적힌 내용을 바탕으로** 답합니다.
이게 바로 RAG 의 핵심입니다 — Cline 이 모르는 내용을 지어내지 않고, 방금
색인한 문서에서 근거를 찾아 답한다는 것입니다. `ask.py` 는 Cline 이 내부적으로
호출하는 것과 **완전히 동일한 코드 경로**(`rag_core.search_documents()`)를
쓰므로, 여기서 본 결과가 곧 Cline 이 받을 결과입니다.

`ask.ps1` 에서 자주 쓰는 옵션:

```powershell
# 결과 개수 조절 (기본 3개)
.\ask.ps1 "청크 크기" --top-k 1

# 검색 모드 지정: hybrid(기본, 의미+키워드) | vector(순수 의미) | keyword(정확한 용어)
.\ask.ps1 "청크 크기" --mode keyword

# 특정 파일만 검색
.\ask.ps1 "연차" --sources docs\example_vacation_policy.md

# 스크립트에서 결과를 이어서 처리하고 싶을 때 (JSON 출력)
.\ask.ps1 "청크 크기" --json
```

> 이미 `.venv` 를 알고 있고 직접 경로를 지정하고 싶다면
> `.\.venv\Scripts\python.exe src\ask.py "질문"` 도 동일하게 동작합니다
> (`ask.ps1` 은 이 명령을 자동으로 대신 해주는 것뿐입니다).

> `score` 값이 낮게(0.03 대) 보이는 이유: 기본 모드가 `hybrid`(벡터+키워드
> RRF 순위 점수)라서 코사인 유사도(0~1)와는 스케일이 다릅니다. 순수 의미
> 유사도 점수가 필요하면 `--mode vector` 로 질의하세요.

### 6-5. 문서를 지웠을 때 (선택)

예시가 끝나면 `docs/example_vacation_policy.md` 를 지우고 다시 색인하면
됩니다. `--prune` 옵션을 쓰면 더 이상 존재하지 않는 파일의 청크를 저장소에서
같이 제거합니다.

```powershell
Remove-Item docs\example_vacation_policy.md
.\.venv\Scripts\python.exe src\ingest.py --prune
```

---

## 자주 묻는 질문 (FAQ)

**Q. 색인된 데이터는 어디에 저장되나요?**
A. 프로젝트 루트의 `rag_store_chroma/` 폴더입니다(Git 에는 올라가지 않습니다).

**Q. 임베딩 모델을 OpenAI 로 바꾸고 싶어요.**
A. `config.json` 의 `embedding.provider` 를 `"openai"` 로 바꾸고,
   환경 변수 `OPENAI_API_KEY` 를 설정한 뒤 `ingest.py --reset` 으로 재색인하세요.
   (임베딩 모델을 바꾸면 벡터 공간이 달라지므로 반드시 재색인이 필요합니다.)

**Q. 검색이 이상하게 나와요 (관련 없는 결과만 나옴).**
A. 문서를 추가/수정한 뒤 재색인을 안 했을 가능성이 큽니다. `python src\ingest.py`
   를 실행해보세요. 그래도 이상하면 `search_docs` 의 `mode` 를 `vector` 로 지정해
   순수 의미 검색만 시도해보세요(기본값은 `hybrid`).

**Q. 서버가 Cline 에서 빨간불(연결 실패)로 나와요.**
A. `command` 경로가 `.venv\Scripts\python.exe` 의 **절대 경로**인지, 오타가 없는지
   확인하세요. 터미널에서 `.\.venv\Scripts\python.exe smoke_mcp.py` 가 통과하는지
   먼저 확인하면 원인을 좁힐 수 있습니다.

**Q. 터미널에서 명령을 실행하면 한글이 깨지거나(`?`, 물음표, 깨진 문자 등)
스크립트가 자꾸 이상하게 동작해요.**
A. Windows PowerShell 이 외부 프로세스(파이썬)의 출력을 콘솔에 표시하거나
   파일로 리다이렉션할 때, 콘솔 코드페이지(`chcp`)와는 별개로
   `$OutputEncoding` / `[Console]::OutputEncoding` 값을 기준으로 바이트를
   해석합니다. 이 값이 UTF-8 이 아니면 `chcp 65001` 을 해도 한글이 깨집니다.
   `ask.ps1` / `ask.cmd` 는 시작할 때 이 값을 **강제로 UTF-8 로 맞추므로**,
   화면 출력이든 `> 결과.txt` 로 리다이렉션이든 항상 한글이 정상으로
   나옵니다. 따라서:
   - 질문할 때는 **`python src\ask.py ...` 를 직접 쓰지 말고 `.\ask.ps1 "질문"`
     (또는 cmd.exe 에서 `ask.cmd "질문"`) 을 쓰세요.**
   - 결과를 파일로 저장하려면 `.\ask.ps1 "질문" > 결과.txt` 처럼 그대로
     리다이렉션해도 됩니다(내부에서 UTF-8 로 이미 맞춰져 있습니다). 단,
     PowerShell 5.1 의 `>` 자체는 파일을 UTF-16LE 로 쓰는 점은 별개
     이슈이니, 다른 프로그램에서 그 파일을 읽을 때는 인코딩을 확인하세요.

**Q. `python src\ask.py "질문"` 을 쳤더니
`ModuleNotFoundError: No module named 'langchain_community'` 가 나요.**
A. 시스템 `python`(예: `C:\Program Files\Python313\python.exe`)으로 실행해서
   생기는 문제입니다. 이 프로젝트의 의존성은 `.venv` 가상환경에만 설치되어
   있습니다. 아래 확인 방법으로 원인을 바로 알 수 있습니다:
   ```powershell
   python -c "import sys; print(sys.executable)"   # .venv 안이 아니면 문제
   ```
   해결 방법은 두 가지입니다.
   1. **`ask.ps1` 을 쓰세요** — `.venv` 를 자동으로 찾아 실행해줍니다:
      `.\ask.ps1 "질문"`
   2. 직접 `.venv` 경로를 지정해서 실행하세요:
      `.\.venv\Scripts\python.exe src\ask.py "질문"`

   같은 이유로 `ingest.py` 나 `rag_server.py` 를 직접 실행할 때도 항상
   `python` 이 아니라 `.\.venv\Scripts\python.exe` 를 써야 합니다.

**Q. 다음에 또 뭘 봐야 하나요?**
A. 검색 모드(`hybrid`/`vector`/`keyword`)의 차이나 버전 관리/릴리스 절차는
   **[README.md](README.md)** 에, 전체 구축 원리와 트러블슈팅은
   **[RAG_STEP_BY_STEP.md](RAG_STEP_BY_STEP.md)** 에 있습니다.
