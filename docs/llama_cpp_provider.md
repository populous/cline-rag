# llama.cpp Embedding Provider 통합 가이드

이 문서는 `src/embeddings_llama_cpp.py`에 추가된 두 provider(`llama_cpp`, `llama_cpp_server`)를
기존 `src/rag_core.py`의 `build_embeddings()`에 연결하는 방법을 설명한다.

이번 PR은 기존 `rag_core.py`, `config.json`, `requirements-optional.txt`를 직접 수정하지 않는다.
리뷰어가 아래 diff 제안을 검토한 뒤 별도 커밋으로 반영하는 것을 권장한다.

## 1. 배경

기존 `build_embeddings()`는 `ollama`/`openai` 두 provider만 지원한다. 로컬에서 순수 llama.cpp
런타임(Ollama 미경유)을 쓰고 싶은 경우를 위해 두 가지 방식을 추가한다.

| provider | 방식 | 필요 의존성 | 특징 |
|---|---|---|---|
| `llama_cpp` | 인프로세스, GGUF 직접 로드 | `llama-cpp-python` (신규) | 서버 불필요, 프로세스당 모델 1개 고정 |
| `llama_cpp_server` | `llama-server`의 OpenAI 호환 `/v1/embeddings` 호출 | 없음 (기존 `langchain-openai` 재사용) | Ollama처럼 서버-클라이언트 분리, 여러 프로세스가 서버 공유 가능 |

## 2. rag_core.py 통합 (제안 diff)

`src/rag_core.py`의 `build_embeddings()` 함수에서 기존 `openai` 분기 뒤에 다음을 추가:

```python
    if provider == "openai":
        ...
        return OpenAIEmbeddings(
            model=conf["model"], api_key=api_key, base_url=conf["apiBase"]
        )

    # --- 신규: llama.cpp 계열 provider는 별도 모듈에 위임 ---
    from embeddings_llama_cpp import supports as _llama_cpp_supports
    from embeddings_llama_cpp import build_llama_cpp_embeddings

    if _llama_cpp_supports(provider):
        return build_llama_cpp_embeddings(cfg)

    raise ValueError(f"알 수 없는 임베딩 제공자: {provider}")
```

`load_config()`의 `DEFAULT_CONFIG["embedding"]`에는 다음을 병합:

```python
from embeddings_llama_cpp import LLAMA_CPP_DEFAULT_CONFIG

DEFAULT_CONFIG = {
    "embedding": {
        "provider": "ollama",
        "ollama": {...},
        "openai": {...},
        **LLAMA_CPP_DEFAULT_CONFIG,  # llama_cpp, llama_cpp_server 기본값 추가
    },
    ...
}
```

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

`requirements-optional.txt`에 다음 추가 (제안):

```
llama-cpp-python   # provider="llama_cpp" 사용 시에만 필요
```

`llama_cpp_server`는 기존 `langchain-openai`를 재사용하므로 추가 의존성이 없다.

## 5. 미결 사항 (리뷰 시 확인 필요)

- [ ] `llama-cpp-python`을 `requirements.txt`(필수) 또는 `requirements-optional.txt`(선택) 중 어디에 둘지 결정
- [ ] GPU 오프로드(`nGpuLayers`) 기본값을 0(CPU)으로 유지할지, 환경 자동 감지로 바꿀지 결정
- [ ] `tests/test_rag_core.py`에 두 provider용 단위 테스트 추가 (기존 `test_load_config_defaults_when_file_missing` 패턴 참고)
- [ ] `ARCHITECTURE.md`의 "로컬 엔진별 색인/검색 능력 차이" 절에 llama.cpp 계열 항목 추가 여부 결정
