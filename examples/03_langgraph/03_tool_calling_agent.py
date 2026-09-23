"""03_tool_calling_agent.py — 도구 호출 루프(agent ↔ tools)의 그래프 구조.

LangGraph 로 에이전트를 만들 때 가장 흔한 패턴이 "모델이 도구 호출을 요청하면
도구를 실행하고, 그 결과를 다시 모델에게 돌려주는" 루프다.

이 예제는 실제 LLM 대신 **결정적 가짜 모델**을 써서, 외부 서비스 없이 그 루프의
그래프 구조를 그대로 보여준다:
    START -> agent -> (도구 호출이 남아 있으면) tools -> agent -> ... -> END
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# (가짜) 도구
# ---------------------------------------------------------------------------
def get_weather(city: str) -> str:
    """도시 날씨를 돌려주는 가짜 도구."""
    return f"{city}: 맑음, 22°C"


# ---------------------------------------------------------------------------
# (가짜) 모델: 정해진 순서대로 답한다
# ---------------------------------------------------------------------------
class ScriptedModel:
    def __init__(self) -> None:
        self.calls = 0

    def respond(self, state: "State") -> dict:
        self.calls += 1
        if self.calls == 1:
            # 1차: 도구 호출을 요청 (function_call 을 발행)
            return {
                "messages": state["messages"] + [
                    {"role": "assistant", "tool_call": ("get_weather", {"city": "서울"})}
                ]
            }
        # 2차: 도구 결과를 받아 최종 답변
        return {
            "messages": state["messages"] + [
                {"role": "assistant", "content": "서울 날씨는 맑음, 22°C 입니다."}
            ]
        }


# ---------------------------------------------------------------------------
# 상태와 노드
# ---------------------------------------------------------------------------
class State(TypedDict):
    messages: list


TOOLS = {"get_weather": get_weather}


def agent_node(state: State) -> dict:
    return model.respond(state)


def tools_node(state: State) -> dict:
    last = state["messages"][-1]
    name, args = last["tool_call"]
    result = TOOLS[name](**args)
    return {"messages": state["messages"] + [{"role": "tool", "content": result}]}


def should_continue(state: State) -> str:
    last = state["messages"][-1]
    if "tool_call" in last:
        return "tools"
    return "end"


model = ScriptedModel()


def main(argv: list[str] | None = None) -> int:
    graph = StateGraph(State)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")

    app = graph.compile()

    print("[실행] 사용자 질문: '서울 날씨 알려줘'")
    result = app.invoke({"messages": [{"role": "user", "content": "서울 날씨 알려줘"}]})

    print("\n[메시지 흐름]")
    for msg in result["messages"]:
        if "tool_call" in msg:
            print(f"  assistant → tool_call: {msg['tool_call']}")
        elif msg["role"] == "tool":
            print(f"  tool      → {msg['content']}")
        else:
            print(f"  {msg['role']:9s} → {msg['content']}")

    print("\n완료: 도구 호출 루프 그래프가 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
