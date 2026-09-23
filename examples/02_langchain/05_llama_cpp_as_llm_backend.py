"""05_llama_cpp_as_llm_backend.py — llama.cpp 를 LangChain 의 LLM 으로 연결.

cline-rag 는 지금 검색(R)만 하고 생성(G)은 Host(OpenCode/Cline)가 맡는다. 이
예제는 "생성"을 llama.cpp 로 직접 하게 만드는 다리 역할을 한다.

LangChain 은 LLM 을 `BaseChatModel`/`BaseLLM` 인터페이스로 추상화한다. llama.cpp
계열은 `langchain_community.llms.LlamaCpp`(구 BaseLLM 계열)로 감싸면, 마치
OpenAI/Anthropic 처럼 동일한 `.invoke()`/`.stream()` 로 호출할 수 있다.

실행:
    python examples\\02_langchain\\05_llama_cpp_as_llm_backend.py --model "C:\\models\\Llama-3.2-1B-Instruct-Q4_K_M.gguf"

사전 준비물이 없으면 정확한 설치/다운로드 방법을 안내하고 종료한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="llama.cpp 를 LangChain LLM 으로 연결")
    parser.add_argument("--model", required=True, help="GGUF 채팅/생성 모델 경로")
    args = parser.parse_args(argv)

    try:
        from llama_cpp import Llama  # noqa: F401  (설치 확인)
    except ImportError:
        print("오류: `llama_cpp` 모듈을 찾을 수 없습니다.", file=sys.stderr)
        print("  python -m pip install -r examples\\requirements-examples.txt", file=sys.stderr)
        return 1

    model_path = Path(args.model)
    if not model_path.is_file():
        print(f"오류: 모델 파일을 찾을 수 없습니다: {args.model}", file=sys.stderr)
        return 1

    try:
        from langchain_community.llms import LlamaCpp
    except ImportError:
        print("오류: `langchain_community` 를 찾을 수 없습니다.", file=sys.stderr)
        print("  python -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    # 1) LangChain 의 LLM 인터페이스로 감싸기
    print(f"[1/2] GGUF 모델을 LangChain LLM 으로 로드: {model_path}")
    llm = LlamaCpp(
        model_path=str(model_path),
        n_ctx=2048,
        n_gpu_layers=0,
        temperature=0.0,
        max_tokens=128,
        verbose=False,
    )

    # 2) 표준 LangChain 프롬프트 + 파서 + LCEL 로 체인 구성
    print("[2/2] 프롬프트 + LLM + StrOutputParser 를 LCEL 로 연결")
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate

    prompt = PromptTemplate.from_template("회사 규정을 근거로 답하세요: {question}")
    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({"question": "반차 8회는 연차로 며칠인가?"})
    print("\n[답변]")
    print(answer.strip())

    print("\n완료: llama.cpp 를 LangChain 의 LLM 으로 연결했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
