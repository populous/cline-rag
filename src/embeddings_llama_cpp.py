"""
embeddings_llama_cpp.py
------------------------
llama.cpp 계열 embedding provider 2종을 위한 독립 팩토리 모듈.

기존 src/rag_core.py 의 build_embeddings() 는 "ollama"/"openai" 두 provider만
지원한다. 이 모듈은 그 함수를 직접 수정하지 않고, 동일한 인터페이스
(cfg: dict -> Embeddings) 를 제공하는 별도 팩토리로 두 provider를 추가한다.
rag_core.py 에 통합하는 방법은 docs/llama_cpp_provider.md 를 참고.

지원 provider:
- "llama_cpp"         : 인프로세스, llama-cpp-python 으로 GGUF 모델 직접 로드.
- "llama_cpp_server"   : llama.cpp 의 llama-server(--embedding 플래그)가 노출하는
                         OpenAI 호환 /v1/embeddings 엔드포인트를 호출.

config.json 예시:
    {
      "embedding": {
        "provider": "llama_cpp_server",
        "llama_cpp": {
          "modelPath": "/models/nomic-embed-text-v1.5.Q8_0.gguf",
          "nCtx": 2048,
          "nGpuLayers": 0,
          "nThreads": null
        },
        "llama_cpp_server": {
          "apiBase": "http://127.0.0.1:8080/v1",
          "apiKey": "not-needed",
          "model": "local-embedding"
        }
      }
    }

의존성:
    llama-cpp-python   # provider="llama_cpp" 사용 시에만 필요 (requirements-optional.txt 에 추가 권장)
    # provider="llama_cpp_server" 는 기존 langchain-openai 를 재사용하므로 추가 의존성 없음.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.embeddings import Embeddings


# rag_core.DEFAULT_CONFIG 에 병합해 넣을 기본값. rag_core.py 통합 시 참고.
LLAMA_CPP_DEFAULT_CONFIG: dict = {
    "llama_cpp": {
        "modelPath": "",
        "nCtx": 2048,
        "nGpuLayers": 0,
        "nThreads": None,
    },
    "llama_cpp_server": {
        "apiBase": "http://127.0.0.1:8080/v1",
        "apiKey": "not-needed",
        "model": "local-embedding",
    },
}


def supports(provider: str) -> bool:
    """이 모듈이 해당 provider 문자열을 처리할 수 있는지 여부."""
    return provider.lower() in ("llama_cpp", "llama_cpp_server")


def build_llama_cpp_embeddings(cfg: dict) -> Embeddings:
    """
    llama.cpp 계열 provider 에 대한 LangChain Embeddings 인스턴스를 만든다.

    cfg 는 rag_core.load_config() 가 반환하는 것과 동일한 스키마의 dict.
    cfg["embedding"]["provider"] 가 "llama_cpp" 또는 "llama_cpp_server" 여야 한다.
    """
    provider = str(cfg["embedding"]["provider"]).lower()

    # --- llama_cpp: 인프로세스, GGUF 직접 로드 ---
    # 별도 서버 기동이 필요 없다. 다만 프로세스당 모델 1개가 고정되므로,
    # ingest.py 와 rag_server.py 를 동시에 띄우면 GGUF 파일이 두 번
    # 메모리에 올라간다는 점에 주의.
    if provider == "llama_cpp":
        from langchain_community.embeddings import LlamaCppEmbeddings

        conf = cfg["embedding"].get("llama_cpp", LLAMA_CPP_DEFAULT_CONFIG["llama_cpp"])
        model_path = conf.get("modelPath", "")
        if not model_path or not Path(model_path).is_file():
            raise RuntimeError(
                f"llama_cpp modelPath 를 찾을 수 없습니다: {model_path!r}. "
                "GGUF 임베딩 모델 경로를 config.json 의 "
                "embedding.llama_cpp.modelPath 에 설정하세요."
            )
        return LlamaCppEmbeddings(
            model_path=model_path,
            n_ctx=conf.get("nCtx", 2048),
            n_gpu_layers=conf.get("nGpuLayers", 0),
            n_threads=conf.get("nThreads", None),
        )

    # --- llama_cpp_server: llama-server, OpenAI 호환 API ---
    # ollama 분기와 동일하게 서버-클라이언트 구조라 여러 프로세스가
    # 하나의 llama-server 인스턴스를 공유할 수 있다. Ollama 없이 순수
    # llama.cpp 런타임만 쓰고 싶을 때 선택.
    if provider == "llama_cpp_server":
        from langchain_openai import OpenAIEmbeddings

        conf = cfg["embedding"].get(
            "llama_cpp_server", LLAMA_CPP_DEFAULT_CONFIG["llama_cpp_server"]
        )
        # 로컬 서버는 보통 API 키 검증을 하지 않으므로 더미 값을 허용한다.
        api_key = conf.get("apiKey", "not-needed")
        # llama-server 의 /v1/models 는 임베딩 컨텍스트 길이(토큰 한도)를 정확히
        # 보고하지 않는다. OpenAIEmbeddings 의 사전 검사를 켜두면 유효한 입력도
        # 조용히 거부되거나 불필요한 추가 요청이 생길 수 있어 끈다.
        return OpenAIEmbeddings(
            model=conf.get("model", "local-embedding"),
            api_key=api_key,
            base_url=conf["apiBase"],
            check_embedding_ctx_length=False,
        )

    raise ValueError(
        f"embeddings_llama_cpp.build_llama_cpp_embeddings 는 "
        f"'llama_cpp'/'llama_cpp_server' 만 지원합니다 (받은 값: {provider!r})."
    )
