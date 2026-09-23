"""02_output_parser.py — LangChain 의 출력 파서(OutputParser).

LLM 이 내뱉는 자유 텍스트를 "구조화된 데이터"로 바꾸는 것이 출력 파서다.
체인 끝에 파서를 붙이면 다음 단계(코드)에서 문자열이 아니라 list/dict 를 받을 수
있다. 여기서는 LLM 없이 파서의 동작만 직접 확인한다.
"""

from __future__ import annotations

from langchain_core.output_parsers import (
    CommaSeparatedListOutputParser,
    StrOutputParser,
)
from langchain_core.prompts import PromptTemplate


def main(argv: list[str] | None = None) -> int:
    # 1) StrOutputParser: 단순 문자열 통과(체인 끝에서 AI 메시지를 문자열로)
    print("[1/3] StrOutputParser (문자열 추출)")
    parser = StrOutputParser()
    # 실제로는 LLM 이 반환한 AIMessage 객체를 문자열로 바꾸는 용도.
    print(f"      parse: {parser.parse('  정리된 답변 텍스트  ')!r}")

    # 2) CommaSeparatedListOutputParser: "a, b, c" -> ["a", "b", "c"]
    print("\n[2/3] CommaSeparatedListOutputParser (쉼표 목록 -> list)")
    list_parser = CommaSeparatedListOutputParser()
    print(f"      parse: {list_parser.parse('연차, 반차, 병가, 경조휴가')}")

    # 3) 프롬프트에 파서의 "형식 지시(format_instructions)"를 주입하는 관례
    print("\n[3/3] 프롬프트에 형식 지시 자동 주입")
    template = PromptTemplate.from_template(
        "휴가 종류를 쉼표로 나열하세요.\n{format_instructions}"
    )
    prompt = template.partial(format_instructions=list_parser.get_format_instructions())
    print("      [프롬프트 렌더링 결과]")
    print(prompt.format())

    print("\n완료: 출력 파서 2종이 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
