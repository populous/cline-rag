# llama.cpp Embedding Provider 통합 가이드

이 문서는 `src/embeddings_llama_cpp.py`에 추가된 두 provider(`llama_cpp`, `llama_cpp_server`)를
기존 `src/rag_core.py`의 `build_embeddings()`에 연결하는 방법을 설명한다.

통합은 이미 반영되어 있다: `rag_core.py`의 `DEFAULT_CONFIG["embedding"]`에 두 provider
기본값이 포함되고, `build_embeddings()`가 llama.cpp 계열 provider를 `embeddings_llama_cpp`
모듈로 위임한다. 아래는 그 구현 요약이다.

## 1. 배경

기존 `build_embeddings()`는 `ollama`/`openai` 두 provider만 지원한다. 로컬에서 순수 llama.cpp
런타임(Ollama 미경유)을 쓰고 싶은 경우를 위해 두 가지 방식을 추가한다.

| provider | 방식 | 필요 의존성 | 특징 |
|---|---|---|---|
| `llama_cpp` | 인프로세스, GGUF 직접 로드 | `llama-cpp-python` (신규) | 서버 불필요, 프로세스당 모델 1개 고정 |
| `llama_cpp_server` | `llama-server`의 OpenAI 호환 `/v1/embeddings` 호출 | 없음 (기존 `langchain-openai` 재사용) | Ollama처럼 서버-클라이언트 분리, 여러 프로세스가 서버 공유 가능 |

## 2. rag_core.py 통합 (완료)

`src/rag_core.py`의 `build_embeddings()` 함수에서 기존 `openai` 분기 뒤에 다음이 추가되어 있다:

```python
    if provider in ("llama_cpp", "llama_cpp_server"):
        from embeddings_llama_cpp import build_llama_cpp_embeddings

        return build_llama_cpp_embeddings(cfg)
    raise ValueError(f"알 수 없는 임베딩 제공자: {provider}")
```

`DEFAULT_CONFIG["embedding"]`에는 `llama_cpp`(`modelPath`, `nCtx`, `nGpuLayers`,
`nThreads`)와 `llama_cpp_server`(`apiBase`, `apiKey`, `model`) 기본값이 인라인으로
포함되어 있다. `config.json`은 이 기본값을 재정의할 때만 수정하면 된다.

## 3. config.json 예시

### 3-1. 인프로세스 (llama_cpp)

```json
{
  "embedding": {
    "provider": "llama_cpp",
    "llama_cpp": {
      "modelPath": "/models/nomic-embed-text-v1.5.Q8_0.gguf",
      "nCtx": 2048,
      "nGpuLayers": 0,
      "nThreads": null
    }
  }
}
```

### 3-2. 서버 API (llama_cpp_server)

```json
{
  "embedding": {
    "provider": "llama_cpp_server",
    "llama_cpp_server": {
      "apiBase": "http://127.0.0.1:8080/v1",
      "apiKey": "not-needed",
      "model": "local-embedding"
    }
  }
}
```

llama-server 기동 예시:

```bash
./llama-server -m /models/nomic-embed-text-v1.5.Q8_0.gguf --embedding --port 8080
```

## 4. 의존성

`requirements-optional.txt`에 다음이 추가되어 있다:

```
llama-cpp-python>=0.3.0   # provider="llama_cpp" 사용 시에만 필요
```

`llama_cpp_server`는 기존 `langchain-openai`를 재사용하므로 추가 의존성이 없다.

## 5. 반영/잔여 사항

- [x] `llama-cpp-python`을 `requirements-optional.txt`(선택)에 추가
- [x] `tests/test_embeddings_llama_cpp.py`에 단위 테스트 추가 (실패 경로/객체 생성, 외부 서비스 불필요)
- [x] `ARCHITECTURE.md`의 "로컬 엔진별 색인/검색 능력 차이" 절에 llama.cpp 계열 언급 추가
- [ ] GPU 오프로드(`nGpuLayers`) 기본값 0(CPU) 유지 여부 — 실제 GPU 환경에서 재검토
