"""02_server_embedding.py — llama-server 의 OpenAI 호환 /v1/embeddings 호출.

이 예제는 cline-rag 메인 앱의 `provider == "llama_cpp_server"` 분기와 동일하다:
    * llama.cpp 의 `llama-server --embedding` 이 노출하는 OpenAI 호환 API 를
    * langchain_openai 의 OpenAIEmbeddings 로 호출(추가 의존성 없음)

서버-클라이언트 구조라서 여러 프로세스가 하나의 llama-server 를 공유할 수 있다.
Ollama 없이 순수 llama.cpp 런타임만 쓰고 싶을 때 이 방식을 쓴다(메인 앱의
업그레이드 로드맵에서 권장하는 방향).

사전 준비:
    1) llama-server 바이너리
    2) GGUF 임베딩 모델
    3) 서버 기동:
       llama-server -m C:\\models\\nomic-embed-text-v1.5.Q8_0.gguf --embedding --port 8080

실행:
    python examples\\01_llama_cpp\\02_server_embedding.py

서버가 꺼져 있으면 정확한 기동 방법을 안내하고 종료한다.
"""

from __future__ import annotations

import sys

API_BASE = "http://127.0.0.1:8080/v1"
MODEL = "local-embedding"


def main(argv: list[str] | None = None) -> int:
    # 1) langchain_openai 가 있는지 확인 (메인 앱 필수 의존성)
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        print("오류: `langchain_openai` 를 찾을 수 없습니다.", file=sys.stderr)
        print("  python -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    # 2) llama-server 가 실제로 떠 있는지 미리 확인 (친절한 안내를 위해)
    try:
        import urllib.request

        urllib.request.urlopen(API_BASE + "/models", timeout=2)
    except Exception:
        print("오류: llama-server 에 연결할 수 없습니다.", file=sys.stderr)
        print(
            "\n먼저 임베딩 서버를 기동하세요:\n"
            "  llama-server -m C:\\models\\nomic-embed-text-v1.5.Q8_0.gguf "
            "--embedding --port 8080\n\n"
            "(llama-server 바이너리는 llama.cpp 저장소를 빌드하거나 공식 릴리스에서 받습니다.)",
            file=sys.stderr,
        )
        return 1

    # 3) OpenAI 호환 엔드포인트를 가리키는 OpenAIEmbeddings 구성
    #    - api_key 는 로컬 서버가 검증하지 않으므로 더미 값
    #    - check_embedding_ctx_length=False: llama-server 가 토큰 한도를
    #      정확히 보고하지 않아 사전 검사를 끈다 (메인 앱과 동일)
    embeddings = OpenAIEmbeddings(
        model=MODEL,
        api_key="not-needed",
        base_url=API_BASE,
        check_embedding_ctx_length=False,
    )

    print("[1/2] 질의 하나를 벡터로 변환 (embed_query)")
    query_vector = embeddings.embed_query("연차는 반차 단위로도 신청할 수 있다")
    print(f"      벡터 차원: {len(query_vector)}")

    print("[2/2] 문서 여러 개를 벡터로 변환 (embed_documents)")
    doc_vectors = embeddings.embed_documents([
        "입사 1년 차부터 매년 15일의 연차가 발생한다.",
        "미사용 연차는 다음 해로 최대 5일까지 이월할 수 있다.",
    ])
    print(f"      문서 수: {len(doc_vectors)}, 각 차원: {len(doc_vectors[0])}")

    print("\n완료: llama-server(OpenAI 호환) 임베딩이 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
