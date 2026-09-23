"""02_conditional_routing.py — 조건부 엣지(add_conditional_edges).

LangGraph 의 핵심은 "현재 상태를 보고 다음 노드를 결정하는" 조건부 분기다.
이 예제는 cline-rag 의 `rag_core.build_search_graph()`가 하는 일을 축소 재현한다:
    * mode == "vector"  -> vector 노드 -> 끝
    * mode == "keyword" -> keyword 노드 -> 끝
    * mode == "hybrid"  -> vector -> keyword -> fuse -> 끝

이 구조를 이해하면 메인 앱의 검색 오케스트레이션이 어떻게 동작하는지 완전히
이해한 셈이다(실제 메인 앱은 여기서 "노드가 검색 결과를 채운다"는 점만 다르다).
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    mode: str
    log: list


def route_mode(state: State) -> str:
    """상태의 mode 값을 그대로 반환해 분기 목적지로 쓴다."""
    return state["mode"]


def node_vector(state: State) -> dict:
    return {"log": state["log"] + ["vector 검색 실행"]}


def node_keyword(state: State) -> dict:
    return {"log": state["log"] + ["keyword 검색 실행"]}


def node_fuse(state: State) -> dict:
    return {"log": state["log"] + ["RRF 융합 실행"]}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("retrieve_vector", node_vector)
    graph.add_node("retrieve_keyword", node_keyword)
    graph.add_node("fuse_hybrid", node_fuse)

    # START 이후 어느 노드로 갈지는 mode 에 따라 결정
    graph.add_conditional_edges(START, route_mode, {
        "vector": "retrieve_vector",
        "keyword": "retrieve_keyword",
        "hybrid": "retrieve_vector",
    })

    # vector 노드 다음: vector 모드면 끝, hybrid 면 keyword 노드로
    graph.add_conditional_edges("retrieve_vector", route_mode, {
        "vector": END,
        "hybrid": "retrieve_keyword",
    })

    # keyword 노드 다음: keyword 모드면 끝, hybrid 면 fuse 노드로
    graph.add_conditional_edges("retrieve_keyword", route_mode, {
        "keyword": END,
        "hybrid": "fuse_hybrid",
    })

    graph.add_edge("fuse_hybrid", END)
    return graph.compile()


def main(argv: list[str] | None = None) -> int:
    app = build_graph()

    for mode in ("vector", "keyword", "hybrid"):
        result = app.invoke({"mode": mode, "log": []})
        flow = " -> ".join(result["log"])
        print(f"[{mode:8s}] {flow}")

    print("\n완료: 조건부 분기 그래프가 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
