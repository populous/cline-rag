# 04. LangSmith — Step by Step

LangSmith 는 LangChain/LangGraph 실행을 **클라우드에 추적(트레이싱)**하고 평가하는
관측성(observability) 도구다. cline-rag 는 아직 LangSmith 를 쓰지 않지만, LangChain
기반이라 언제든 켤 수 있다. 이 폴더는 그 방법을 익힌다.

## 사전 준비물

1. [smith.langchain.com](https://smith.langchain.com) 가입 + **API 키 발급**
   (형식: `lsv2_pt_...`)
2. 워크스페이스 루트에 `.env` 파일 생성 (이미 만들어 둔 상태 가정):

   ```env
   LANGSMITH_API_KEY=발급받은_키
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_PROJECT=cline-rag-examples
   ```

   > `.env` 는 `.gitignore` 에 등록되어 있어 git 에 절대 커밋되지 않는다.
   > 키 없이 참고만 하려면 `examples\.env.example` 을 보면 된다.

## 이 폴더에서 배우는 것

| 파일 | 개념 |
|---|---|
| [`01_enable_tracing.py`](01_enable_tracing.py) | `.env` 로드 → `@traceable`/체인 트레이싱 켜기 |
| [`02_trace_langgraph_run.py`](02_trace_langgraph_run.py) | LangGraph 실행을 LangSmith 에 추적 |
| [`03_simple_eval_dataset.py`](03_simple_eval_dataset.py) | 평가용 데이터셋 생성/조회 기초 |

## 실행

```powershell
python examples\04_langsmith\01_enable_tracing.py
python examples\04_langsmith\02_trace_langgraph_run.py
python examples\04_langsmith\03_simple_eval_dataset.py
```

`.env` 에 키가 없으면 각 스크립트는 정확한 준비 방법을 안내하고 종료한다.

## 주의

- 실제로 실행하면 LangSmith 프로젝트(`cline-rag-examples`)에 **트레이스가
  기록**된다(무료 플랜으로 시작 가능). 원치 않으면 `.env` 의
  `LANGCHAIN_TRACING_V2=false` 로 두면 된다.
