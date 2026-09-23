"""01_inprocess_embedding.py — llama.cpp 를 "프로세스 안에서" 직접 로드해 임베딩.

이 예제는 cline-rag 메인 앱의 `src/embeddings_llama_cpp.py` 에서
`provider == "llama_cpp"` 분기가 내부적으로 하는 일과 동일하다:
    * llama-cpp-python 의 LlamaCppEmbeddings 로 GGUF 모델을 직접 로드
    * embed_query / embed_documents 로 텍스트를 벡터로 변환

"프로세스 안에서(in-process)"란, 별도 서버(예: llama-server)를 띄우지 않고
이 파이썬 프로세스가 GGUF 파일을 직접 메모리에 올린다는 뜻이다. 장점은 서버
기동이 필요 없다는 것이고, 단점은 프로세스당 모델이 1개로 고정되어 여러
프로세스(ingest.py, rag_server.py)가 각자 모델을 중복 로딩한다는 것이다.

실행:
    python examples\\01_llama_cpp\\01_inprocess_embedding.py --model "C:\\models\\nomic-embed-text-v1.5.Q8_0.gguf"

사전 준비물이 없으면 정확한 설치/다운로드 방법을 안내하고 종료한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _install_hint() -> str:
    return (
        "예제 전용 의존성을 설치하세요:\n"
        "  python -m pip install -r examples\\requirements-examples.txt\n\n"
        "그리고 GGUF 임베딩 모델을 준비하세요. 예:\n"
        "  https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF\n"
        "  → nomic-embed-text-v1.5.Q8_0.gguf"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="llama.cpp 인프로세스 임베딩 예제")
    parser.add_argument("--model", required=True, help="GGUF 임베딩 모델 경로")
    args = parser.parse_args(argv)

    # 1) llama-cpp-python 이 설치되어 있는지 확인 (없으면 안내 후 종료)
    try:
        from llama_cpp import Llama  # noqa: F401  (설치 확인용)
    except ImportError:
        print("오류: `llama_cpp` 모듈을 찾을 수 없습니다.", file=sys.stderr)
        print(_install_hint(), file=sys.stderr)
        return 1

    # 2) GGUF 모델 파일 존재 확인
    model_path = Path(args.model)
    if not model_path.is_file():
        print(
            f"오류: 모델 파일을 찾을 수 없습니다: {args.model}\n"
            "다운로드한 GGUF 모델의 실제 경로를 --model 로 넘기세요.",
            file=sys.stderr,
        )
        return 1

    # 3) LangChain 의 LlamaCppEmbeddings 로 로드 (메인 앱과 동일한 방식)
    #    참고: cline-rag 의 embeddings_llama_cpp.py 는 langchain_community 의
    #    LlamaCppEmbeddings 를 쓴다.
    try:
        from langchain_community.embeddings import LlamaCppEmbeddings
    except ImportError:
        print("오류: `langchain_community` 를 찾을 수 없습니다.", file=sys.stderr)
        print(_install_hint(), file=sys.stderr)
        return 1

    print(f"[1/3] GGUF 모델 로드 중: {model_path}")
    embeddings = LlamaCppEmbeddings(
        model_path=str(model_path),
        n_ctx=2048,          # 컨텍스트(토큰) 길이
        n_gpu_layers=0,      # 0 = CPU 전용. GPU 오프로드는 실제 GPU 환경에서 조정
        n_threads=None,      # None = 자동
    )

    print("[2/3] 질의 하나를 벡터로 변환 (embed_query)")
    query_vector = embeddings.embed_query("연차는 반차 단위로도 신청할 수 있다")
    print(f"      벡터 차원: {len(query_vector)}")
    print(f"      앞 5개 값: {query_vector[:5]}")

    print("[3/3] 문서 여러 개를 벡터로 변환 (embed_documents)")
    docs = [
        "입사 1년 차부터 매년 15일의 연차가 발생한다.",
        "미사용 연차는 다음 해로 최대 5일까지 이월할 수 있다.",
    ]
    doc_vectors = embeddings.embed_documents(docs)
    print(f"      문서 수: {len(doc_vectors)}, 각 차원: {len(doc_vectors[0])}")

    print("\n완료: llama.cpp 로 임베딩(벡터화)이 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
