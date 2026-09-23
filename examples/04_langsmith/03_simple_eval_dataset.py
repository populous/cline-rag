"""03_simple_eval_dataset.py — LangSmith 평가용 데이터셋 기초.

LangSmith 는 (입력, 정답) 쌍으로 구성된 데이터셋을 만들어 체인/에이전트를 평가할
수 있다. 이 예제는 작은 데이터셋을 만들고 조회하는 기초다.

키가 없으면 정확한 준비 방법을 안내하고 종료한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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
        print("워크스페이스 루트의 .env 에 LANGSMITH_API_KEY 를 채우세요.", file=sys.stderr)
        return 1

    try:
        from langsmith import Client
    except ImportError:
        print("오류: `langsmith` 가 없습니다.", file=sys.stderr)
        print("  python -m pip install -r examples\\requirements-examples.txt", file=sys.stderr)
        return 1

    client = Client()
    dataset_name = "cline-rag-vacation-qa"

    examples = [
        {"question": "반차 8회는 연차로 며칠인가?", "answer": "연차 4일"},
        {"question": "반차 1회는 연차로 얼마인가?", "answer": "연차 0.5일"},
    ]

    print(f"[데이터셋 준비] {dataset_name}")
    try:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="cline-rag 예제: 휴가 규정 질의응답 평가용",
        )
        for ex in examples:
            client.create_example(
                inputs={"question": ex["question"]},
                outputs={"answer": ex["answer"]},
                dataset_id=dataset.id,
            )
        print(f"  생성/추가 완료: {len(examples)}개 예제")
    except Exception as exc:  # noqa: BLE001
        print(f"  데이터셋 작업 실패(이미 존재하거나 권한/네트워크 문제): {exc}", file=sys.stderr)

    # 조회 확인
    print("\n[데이터셋 목록]")
    for ds in client.list_datasets():
        print(f"  - {ds.name}")

    print("\n완료: LangSmith 데이터셋 기초를 확인했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
