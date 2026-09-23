"""03_inprocess_text_generation.py — llama.cpp 로 "텍스트 생성(답변 생성)".

현재 cline-rag 메인 앱은 검색(R)만 담당하고, 최종 답변 생성(G)은 Host(OpenCode/Cline)가
맡는다. 즉 메인 앱에는 "llama.cpp 로 텍스트를 생성하는" 코드가 아직 없다.

이 예제는 그 공백을 채우는 출발점이다. "llama.cpp 업그레이드" 로드맵(05_upgrade_path)
에서, MCP 호스트 없이도 cline-rag 스스로 답변까지 생성하는 요구사항이 생기면
여기 있는 패턴(채팅 포맷 + completion)을 그대로 재사용하면 된다.

실행:
    python examples\\01_llama_cpp\\03_inprocess_text_generation.py --model "C:\\models\\Llama-3.2-1B-Instruct-Q4_K_M.gguf"

사전 준비물이 없으면 정확한 설치/다운로드 방법을 안내하고 종료한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="llama.cpp 인프로세스 텍스트 생성 예제")
    parser.add_argument("--model", required=True, help="GGUF 채팅/생성 모델 경로")
    args = parser.parse_args(argv)

    try:
        from llama_cpp import Llama
    except ImportError:
        print("오류: `llama_cpp` 모듈을 찾을 수 없습니다.", file=sys.stderr)
        print(
            "  python -m pip install -r examples\\requirements-examples.txt\n"
            "그리고 GGUF 채팅 모델을 준비하세요. 예:\n"
            "  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF",
            file=sys.stderr,
        )
        return 1

    model_path = Path(args.model)
    if not model_path.is_file():
        print(f"오류: 모델 파일을 찾을 수 없습니다: {args.model}", file=sys.stderr)
        return 1

    print(f"[1/2] GGUF 채팅 모델 로드 중: {model_path}")
    llm = Llama(
        model_path=str(model_path),
        n_ctx=2048,
        n_gpu_layers=0,   # CPU 전용 (GPU 있으면 올리면 됨)
        verbose=False,
    )

    print("[2/2] 답변 생성 (create_chat_completion)")
    # llama.cpp 는 OpenAI 호환 채팅 포맷을 지원한다.
    messages = [
        {"role": "system", "content": "너는 사내 규정을 친절히 설명하는 비서다."},
        {"role": "user", "content": "반차 8회는 연차로 며칠인가?"},
    ]
    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=128,
        temperature=0.0,
    )

    answer = response["choices"][0]["message"]["content"]
    print("\n[답변]")
    print(answer)

    print("\n완료: llama.cpp 로 텍스트 생성이 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
