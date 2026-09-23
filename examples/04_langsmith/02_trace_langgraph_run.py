"""02_trace_langgraph_run.py — LangGraph 실행을 LangSmith 에 추적.

트레이싱을 켜두면 LangGraph 그래프의 각 노드 실행이 LangSmith 에 자동으로
기록된다. 여기서는 03_langgraph 의 최소 그래프를 그대로 실행해 추적한다.

키가 없으면 정확한 준비 방법을 안내하고 종료한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TypedDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _load_env() -> bool:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("오류: `python-dotenv` 가 없습니다.", file=sys.stderr)
        print("  python -m pip install -r examples\\requirements-examples.txt", file=sys.stderr)
        return False
    load_dotenv(ENV_FILE)
    return True


class State(TypedDict):
    text: str
    count: int


def node_a(state: State) -> dict:
    return {"text": state["text"] + "-A"}


def node_b(state: State) -> dict:
    return {"count": state["count"] + 1, "text": state["text"] + "-B"}


def main(argv: list[str] | None = None) -> int:
    if not _load_env():
        return 1

    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key or api_key.startswith("여기에_"):
        print("오류: LANGSMITH_API_KEY 가 설정되지 않았습니다.", file=sys.stderr)
        print("워크스페이스 루트의 .env 에 LANGSMITH_API_KEY 를 채우세요.", file=sys.stderr)
        return 1

    os.environ["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "cline-rag-examples")

    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(State)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    app = graph.compile()

    print("[LangGraph 실행 (트레이싱 켜짐)]")
    result = app.invoke({"text": "start", "count": 0})
    print(f"  결과: {result}")

    print("\n완료: LangSmith 에서 이 실행의 노드별 트레이스를 확인할 수 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
