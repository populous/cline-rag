"""01_minimal_state_graph.py — LangGraph 의 최소 그래프.

LangGraph 는 "상태(State)를 노드가 갱신하고, 엣지가 흐름을 결정하는" 유한 상태
그래프다. 이 예제는 가장 작은 형태를 보여준다:
    START -> [노드A] -> [노드B] -> END

각 노드는 현재 상태를 받아 "갱신할 일부 키"를 dict 로 돌려주고, LangGraph 가
이를 상태에 병합한다. 상태 스키마는 TypedDict 로 선언한다.

cline-rag 의 rag_core.SearchState 와 같은 패턴이다.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# 1) 상태 스키마 (그래프 전체가 공유하는 데이터 구조)
class State(TypedDict):
    text: str
    count: int


# 2) 노드 = 상태를 받아 일부 키를 갱신하는 순수 함수
def node_append(state: State) -> dict:
    return {"text": state["text"] + "-A"}


def node_increment(state: State) -> dict:
    return {"count": state["count"] + 1}


def node_append_b(state: State) -> dict:
    return {"text": state["text"] + "-B"}


def main(argv: list[str] | None = None) -> int:
    # 3) 그래프 구성
    graph = StateGraph(State)
    graph.add_node("append_a", node_append)
    graph.add_node("increment", node_increment)
    graph.add_node("append_b", node_append_b)

    graph.add_edge(START, "append_a")
    graph.add_edge("append_a", "increment")
    graph.add_edge("increment", "append_b")
    graph.add_edge("append_b", END)

    app = graph.compile()

    # 4) 실행 (초기 상태를 넣으면 최종 상태가 나온다)
    print("[입력]  {'text': 'start', 'count': 0}")
    result = app.invoke({"text": "start", "count": 0})
    print(f"[결과]  {result}")

    print("\n완료: 최소 LangGraph 가 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
