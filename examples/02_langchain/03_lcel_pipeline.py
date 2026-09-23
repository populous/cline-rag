"""03_lcel_pipeline.py — LCEL(LangChain Expression Language) 파이프라인.

LCEL 은 LangChain 의 핵심 조합 문법이다. 모든 컴포넌트가 `Runnable` 인터페이스를
구현하고, `|`(파이프) 연산자로 이어붙이면 하나의 `Runnable` 체인이 된다.
체인은 그 자체로 다시 Runnable 이라서, `.invoke()`, `.batch()`, `.stream()` 등을
공통으로 쓸 수 있다.

여기서는 LLM 없이 순수 함수(RunnableLambda)로 파이프라인을 구성해 LCEL 의
작동 원리를 확인한다.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough


def upper(text: str) -> str:
    return text.upper()


def add_bang(text: str) -> str:
    return text + "!"


def main(argv: list[str] | None = None) -> int:
    # 1) 단순 체인: input -> upper -> add_bang
    print("[1/3] 단순 체인 (| 파이프 연산자)")
    chain = RunnableLambda(upper) | RunnableLambda(add_bang)
    print(f"      invoke('hello') -> {chain.invoke('hello')}")

    # 2) RunnablePassthrough: 입력을 그대로 통과 + 병렬(RunnableParallel)
    print("\n[2/3] 병렬 분기 (RunnableParallel + RunnablePassthrough)")
    parallel = RunnableParallel(
        original=RunnablePassthrough(),
        upper=RunnableLambda(upper),
        bang=RunnableLambda(add_bang),
    )
    print(f"      invoke('rag') -> {parallel.invoke('rag')}")

    # 3) dict 입출력 + 배치(batch) — 실제 RAG 체인의 형태와 유사
    print("\n[3/3] dict 입출력 + batch (여러 입력 한 번에)")
    def build_greeting(item: dict) -> str:
        return f"{item['greeting']}, {item['name']}"

    greet_chain = RunnableLambda(build_greeting)
    results = greet_chain.batch([
        {"greeting": "안녕하세요", "name": "김영기"},
        {"greeting": "환영합니다", "name": "새 사용자"},
    ])
    for r in results:
        print(f"      {r}")

    print("\n완료: LCEL 파이프라인이 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
