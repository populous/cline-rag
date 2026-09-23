"""01_prompt_template.py — LangChain 의 PromptTemplate (프롬프트 추상화).

LangChain 의 첫 관문은 "프롬프트를 객체로 다루는 것"이다. 문자열을 직접
이어붙이지 않고 PromptTemplate 로 변수 자리만 남겨두면, 같은 틀을 여러 입력에
재사용할 수 있다. 여기서는 외부 LLM 없이 순수하게 템플릿 렌더링만 확인한다.

cline-rag 메인 앱은 LLM 프롬프트를 직접 다루지 않지만(검색만 담당), LangChain
기반 확장(예: 05_llama_cpp_as_llm_backend.py)을 할 때 이 개념이 필수다.
"""

from __future__ import annotations

from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)


def main(argv: list[str] | None = None) -> int:
    # 1) 단순 문자열 템플릿
    print("[1/3] PromptTemplate (단순 변수 치환)")
    template = PromptTemplate.from_template(
        "회사 규정을 참고해서 다음 질문에 답하세요: {question}"
    )
    rendered = template.format(question="반차 8회는 연차로 며칠인가?")
    print(f"      결과: {rendered}")

    # 2) 여러 변수 + 부분 채우기
    print("\n[2/3] 여러 변수와 partial(부분 미리 채움)")
    template2 = PromptTemplate.from_template(
        "{role}로서 다음을 {tone}하게 요약하세요:\n{text}"
    )
    partial = template2.partial(role="인사 담당자", tone="간결")
    print(f"      결과: {partial.format(text='연차는 반차 단위로도 신청할 수 있다.')}")

    # 3) 채팅 템플릿(system/human 분리) — 실제 LLM 호출 예제에서 쓰는 형태
    print("\n[3/3] ChatPromptTemplate (system/human 메시지 분리)")
    chat = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template("너는 {role}다."),
        HumanMessagePromptTemplate.from_template("{question}"),
    ])
    messages = chat.format_messages(role="사내 규정 비서", question="반차는 몇 시간인가?")
    for msg in messages:
        print(f"      [{msg.type}] {msg.content}")

    print("\n완료: 프롬프트 템플릿 3종이 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
