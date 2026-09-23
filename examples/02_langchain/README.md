# 02. LangChain — Step by Step

`cline-rag` 메인 앱의 임베딩·벡터 저장소·리트리버·청킹은 모두 **LangChain**
컴포넌트로 구현되어 있다. 이 폴더는 LangChain의 핵심 개념을, 외부 서비스 없이
돌아가는 예제부터 메인 앱과 연결되는 예제까지 단계별로 익힌다.

## 이 폴더에서 배우는 것

| 파일 | 개념 | 외부 서비스 필요? |
|---|---|---|
| [`01_prompt_template.py`](01_prompt_template.py) | `PromptTemplate` (프롬프트 추상화/변수 치환) | ❌ 없음 |
| [`02_output_parser.py`](02_output_parser.py) | `StrOutputParser`, `CommaSeparatedListOutputParser` (출력 정형화) | ❌ 없음 |
| [`03_lcel_pipeline.py`](03_lcel_pipeline.py) | LCEL(`\|` 파이프 연산자, `RunnableLambda`, `RunnablePassthrough`, `RunnableParallel`) | ❌ 없음 |
| [`04_retriever_with_chroma.py`](04_retriever_with_chroma.py) | `BM25Retriever` / Chroma `as_retriever` 로 메인 앱 저장소 재사용 | 메인 앱 색인(Ollama) 필요 |
| [`05_llama_cpp_as_llm_backend.py`](05_llama_cpp_as_llm_backend.py) | llama.cpp 를 LangChain 의 LLM 으로 연결 | `llama-cpp-python` + GGUF |

## 실행

```powershell
# 01~03 은 외부 서비스 없이 즉시 실행 가능
python examples\02_langchain\01_prompt_template.py
python examples\02_langchain\02_output_parser.py
python examples\02_langchain\03_lcel_pipeline.py

# 04 는 메인 앱이 색인되어 있어야 한다 (python src\ingest.py 로 색인)
python examples\02_langchain\04_retriever_with_chroma.py

# 05 는 llama.cpp 필요
python examples\02_langchain\05_llama_cpp_as_llm_backend.py --model "C:\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
```

## cline-rag 와의 관계

- `01~03`은 LangChain 의 순수 구성요소라서, `src/rag_core.py`가 이들을 어떻게
  조합하는지 이해하는 기초가 된다.
- `04`는 메인 앱의 Chroma 저장소를 "읽기 전용"으로 열어 리트리버로 쓰는 법을
  보여준다 — 이게 곧 `rag_core.search()`/`keyword_search()`의 내부와 같다.
- `05`는 "llama.cpp 를 생성(LLM)에도 쓰자"는 업그레이드 로드맵의 핵심 다리다.
