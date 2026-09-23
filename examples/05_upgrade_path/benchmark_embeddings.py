"""benchmark_embeddings.py — Ollama vs llama_cpp_server 임베딩 벤치마크.

메인 앱의 임베딩 엔진을 llama.cpp 로 전환하기 전에, 기존 Ollama 와 llama.cpp
서버의 임베딩 속도·벡터 일관성을 간단히 비교한다. 메인 앱의 rag_core 를
"읽기 전용"으로 재사용한다(색인/저장소는 변경하지 않음).

사전 준비:
    # llama-server (임베딩 모드) 를 별도로 기동
    llama-server -m C:\\models\\nomic-embed-text-v1.5.Q8_0.gguf --embedding --port 8080

실행:
    python examples\05_upgrade_path\benchmark_embeddings.py

llama-server 가 꺼져 있으면 그 부분만 안내하고 Ollama 부분은 계속 진행한다.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

import rag_core as core  # noqa: E402


SAMPLE_TEXTS = [
    "입사 1년 차부터 매년 15일의 연차가 발생한다.",
    "미사용 연차는 다음 해로 최대 5일까지 이월할 수 있다.",
    "연차는 반차(0.5일) 단위로도 신청할 수 있다.",
]


def _time_embed(embeddings, texts: list[str], runs: int = 3) -> tuple[float, int]:
    """여러 문서를 여러 번 임베딩해 평균 소요 시간(초)과 벡터 차원을 돌려준다."""
    start = time.perf_counter()
    dim = 0
    for _ in range(runs):
        vectors = embeddings.embed_documents(texts)
        dim = len(vectors[0])
    elapsed = time.perf_counter() - start
    return elapsed / runs, dim


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def main(argv: list[str] | None = None) -> int:
    cfg = core.load_config()

    # 1) Ollama (현재 기본)
    print("== Ollama (현재 기본 provider) ==")
    try:
        ollama_emb = core.build_embeddings(cfg)
        elapsed, dim = _time_embed(ollama_emb, SAMPLE_TEXTS)
        print(f"  평균 {elapsed:.4f}초 / 벡터 차원 {dim}")
        ollama_vecs = ollama_emb.embed_documents(SAMPLE_TEXTS)
    except Exception as exc:  # noqa: BLE001
        print(f"  Ollama 실패: {exc}", file=sys.stderr)
        ollama_vecs = None

    # 2) llama_cpp_server
    print("== llama_cpp_server (후보 provider) ==")
    try:
        from langchain_openai import OpenAIEmbeddings

        llama_emb = OpenAIEmbeddings(
            model="local-embedding",
            api_key="not-needed",
            base_url="http://127.0.0.1:8080/v1",
            check_embedding_ctx_length=False,
        )
        elapsed, dim = _time_embed(llama_emb, SAMPLE_TEXTS)
        print(f"  평균 {elapsed:.4f}초 / 벡터 차원 {dim}")
        llama_vecs = llama_emb.embed_documents(SAMPLE_TEXTS)
    except Exception as exc:  # noqa: BLE001
        print("  llama-server 미연결 또는 오류:", exc, file=sys.stderr)
        print("  llama-server -m <gguf> --embedding --port 8080 로 기동하세요.", file=sys.stderr)
        llama_vecs = None

    # 3) 벡터 일관성 비교 (두 엔진이 모두 준비됐을 때만)
    if ollama_vecs and llama_vecs:
        print("\n== 벡터 일관성 (같은 문장 쌍의 코사인 유사도) ==")
        for a, b in zip(ollama_vecs, llama_vecs):
            # 참고: 서로 다른 런타임이 같은 GGUF 를 써도 수치 차이가 있을 수 있다.
            print(f"  cosine(Ollama, llama_cpp) = {_cosine(a, b):.4f}")

    print("\n완료: 벤치마크가 끝났습니다. 결과를 보고 provider 전환 여부를 결정하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
