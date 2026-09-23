# examples — `cline-rag` 서브 학습 프로젝트

이 폴더는 `cline-rag` 메인 잡(`src/`, `tests/`, `config.json`)을 **전혀 건드리지
않고**, 메인 앱을 구성하는 기술들을 처음부터 끝까지 따라 하며 완전히 이해하기
위한 **서브 학습 프로젝트**다. 각 폴더가 하나의 기술을 다루며, 번호 순서대로
진행하면 자연스럽게 연결된다.

> 메인 앱이 무엇인지는 **[../ARCHITECTURE.md](../ARCHITECTURE.md)** 를,
> 설치/사용법은 **[../GETTING_STARTED.md](../GETTING_STARTED.md)** 를 참고한다.

## 학습 순서

| 순서 | 폴더 | 다루는 것 | 메인 앱과의 관계 |
|---|---|---|---|
| 1 | [`01_llama_cpp/`](01_llama_cpp/) | llama.cpp: GGUF 로드, 임베딩, 텍스트 생성, llama-server | 메인 앱의 임베딩 엔진(v2.2.0부터 도입) |
| 2 | [`02_langchain/`](02_langchain/) | LangChain: 프롬프트/파서/LCEL/리트리버, llama.cpp를 LLM으로 | 메인 앱의 임베딩·저장소·리트리버를 감싸는 프레임워크 |
| 3 | [`03_langgraph/`](03_langgraph/) | LangGraph: StateGraph/조건부 엣지/도구 호출/검색+생성 그래프 | 메인 앱의 검색 오케스트레이션(hybrid 분기) |
| 4 | [`04_langsmith/`](04_langsmith/) | LangSmith: 트레이싱/실행 추적/평가 데이터셋 | 실행 관측성(observability) 담당 |
| 5 | [`05_upgrade_path/`](05_upgrade_path/) | llama.cpp를 메인 엔진으로 승격하는 로드맵 | **향후 개발 방향** |

## 시작하기

```powershell
cd C:\path\to\cline-rag

# 1) 예제 전용 의존성 설치 (메인 앱 요구사항과 분리되어 있음)
python -m pip install -r examples/requirements-examples.txt
```

각 폴더의 `README.md`가 사전 준비물과 실행 순서를 안내한다.

## 원칙

1. **메인 잡 무수정**: 이 폴더의 어떤 예제도 `src/`, `tests/`, `config.json`,
   `requirements*.txt`(메인), `CMakeLists.txt`, `pytest.ini`, CI 를 바꾸지 않는다.
2. **의존성 분리**: 예제에 필요한 패키지는 `examples/requirements-examples.txt`로만
   관리한다.
3. **읽기 전용 재사용**: 메인 앱의 `rag_core.py`를 import 하는 예제(리트리버, RAG
   그래프, 벤치마크)는 저장소를 **조회만** 하고 색인/삭제 등 상태 변경을 하지 않는다.
4. **외부 서비스 없으면 안내**: `llama-cpp-python`, `llama-server`, GGUF 모델,
   LangSmith 키 등이 없으면 스택 트레이스를 내지 않고 정확한 준비 방법을 안내한 뒤
   깔끔하게 종료한다(메인 앱 `ask.py` 의 관례와 동일).
5. **CI 영향 없음**: `pytest.ini`의 `testpaths = tests` 때문에 이 폴더는 pytest/CTest
   자동 실행 대상이 아니며, GitHub Actions CI 에도 영향이 없다.
