# 03. LangGraph — Step by Step

`cline-rag` 의 검색 오케스트레이션(`vector`/`keyword`/`hybrid` 모드 분기)은
**LangGraph** 의 `StateGraph`로 구현되어 있다(`src/rag_core.py`의
`build_search_graph()`). 이 폴더는 LangGraph 의 핵심 개념을 작은 예제로 익힌다.

## 이 폴더에서 배우는 것

| 파일 | 개념 | 외부 서비스 필요? |
|---|---|---|
| [`01_minimal_state_graph.py`](01_minimal_state_graph.py) | `StateGraph`, 노드, 엣지, `START`/`END`, 상태(TypedDict) | ❌ 없음 |
| [`02_conditional_routing.py`](02_conditional_routing.py) | `add_conditional_edges` — 메인 앱의 모드 분기와 동일한 패턴 | ❌ 없음 |
| [`03_tool_calling_agent.py`](03_tool_calling_agent.py) | 도구 호출 루프(agent → tools → 반복) — 결정적 가짜 LLM 으로 시연 | ❌ 없음 |
| [`04_rag_graph_with_llama_cpp.py`](04_rag_graph_with_llama_cpp.py) | 검색(메인 앱 Chroma 재사용) + 생성(llama.cpp) 을 잇는 완결형 RAG 그래프 | 메인 앱 색인 + llama.cpp |

## 실행

```powershell
# 01~03 은 외부 서비스 없이 즉시 실행 가능
python examples\03_langgraph\01_minimal_state_graph.py
python examples\03_langgraph\02_conditional_routing.py
python examples\03_langgraph\03_tool_calling_agent.py

# 04 는 검색(메인 앱 색인) + 생성(llama.cpp) 필요
python examples\03_langgraph\04_rag_graph_with_llama_cpp.py --model "C:\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
```

## cline-rag 와의 관계

- `02_conditional_routing.py` 는 `rag_core.build_search_graph()`의 분기 로직을
  축소 재현한 것이므로, 이걸 이해하면 메인 앱의 검색 오케스트레이션을 완전히
  이해한 셈이다.
- `04_rag_graph_with_llama_cpp.py` 는 현재 메인 앱이 "검색(R)만" 하는 것을
  "검색+생성(RAG)"으로 확장하는 형태라, 업그레이드 로드맵의 핵심 참고 구현이다.
