"""01_enable_tracing.py — LangSmith 트레이싱 켜기.

워크스페이스 루트의 .env 를 읽어 LangSmith 를 활성화하고, `@traceable` 데코레이터로
함수 실행을 추적하는 최소 예제다. 키가 없으면 정확한 준비 방법을 안내하고 종료한다.

주의: 실제로 실행하면 LangSmith 프로젝트에 트레이스가 기록된다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 워크스페이스 루트(.env 위치)를 명시적으로 지정해 어디서 실행해도 동일하게 로드
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


def main(argv: list[str] | None = None) -> int:
    if not _load_env():
        return 1

    api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not api_key or api_key.startswith("여기에_"):
        print("오류: LANGSMITH_API_KEY 가 설정되지 않았습니다.", file=sys.stderr)
        print(
            "워크스페이스 루트의 .env 에 다음을 채우세요 (예제는 examples\\.env.example 참고):\n"
            "  LANGSMITH_API_KEY=발급받은_키\n"
            "  LANGCHAIN_TRACING_V2=true\n"
            "  LANGCHAIN_PROJECT=cline-rag-examples",
            file=sys.stderr,
        )
        return 1

    # LangSmith 는 표준 환경변수를 자동으로 읽는다 (V2 트레이싱)
    os.environ["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "cline-rag-examples")

    # 1) @traceable 로 순수 함수를 추적 대상으로 표시
    from langsmith import traceable

    @traceable(run_type="chain")
    def answer_with_context(question: str, context: str) -> str:
        # 실제로는 LLM 호출 등이 들어가는 자리. 여기선 결정적으로 동작.
        return f"[{context}] 를 근거로 답: {question}"

    print(f"[트레이싱 켜짐] project = {os.environ['LANGCHAIN_PROJECT']}")
    print(f"[traceable 함수 호출] {answer_with_context('반차 8회는?', '반차 1회=0.5일')}")

    print("\n완료: LangSmith 트레이싱이 활성화되었습니다.")
    print("smith.langchain.com 에서 방금 실행한 트레이스를 확인할 수 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
