# 01. llama.cpp — Step by Step

`llama.cpp`는 GGUF 형식의 로컬 LLM/임베딩 모델을 CPU(+선택 GPU)로 돌리는 C/C++
런타임이다. 이 폴더는 `cline-rag`가 v2.2.0부터 임베딩 엔진으로 쓰기 시작한
llama.cpp를, 임베딩과 텍스트 생성 양쪽 관점에서 처음부터 이해하기 위한 예제다.

## 이 폴더에서 배우는 것

| 파일 | 무엇을 하는가 | 필요한 것 |
|---|---|---|
| [`01_inprocess_embedding.py`](01_inprocess_embedding.py) | `llama-cpp-python`으로 GGUF 임베딩 모델을 **프로세스 안에서** 직접 로드해 벡터화 | `llama-cpp-python` + GGUF 임베딩 모델 |
| [`02_server_embedding.py`](02_server_embedding.py) | `llama-server`(OpenAI 호환 `/v1/embeddings`)를 호출해 임베딩 | `llama-server` 바이너리 + GGUF 모델 |
| [`03_inprocess_text_generation.py`](03_inprocess_text_generation.py) | llama.cpp로 **텍스트 생성**(현재 cline-rag에는 없는 영역) | `llama-cpp-python` + GGUF 채팅 모델 |

## 사전 준비물

### 1) 예제 의존성 설치
```powershell
python -m pip install -r examples/requirements-examples.txt
```

### 2) GGUF 모델 준비 (예: Hugging Face에서 다운로드)

- **임베딩 모델** 예: `nomic-ai/nomic-embed-text-v1.5-GGUF` 의
  `nomic-embed-text-v1.5.Q8_0.gguf`
- **채팅 모델** 예: `bartowski/Llama-3.2-1B-Instruct-GGUF` 의 Q4_K_M 파일

다운로드 후 실제 경로를 `MODEL_PATH` 로 넘기면 된다.

### 3) `llama-server` 바이너리 (02 번 예제에서만 필요)

llama.cpp 저장소(https://github.com/ggml-org/llama.cpp)를 빌드하거나, 공식 릴리스
바이너리를 받아 `llama-server` 를 PATH 에 두면 된다.

## cline-rag 와의 관계

이 폴더의 예제 01/02 는 메인 앱의 `src/embeddings_llama_cpp.py`가 내부적으로 하는
일과 동일하다(`llama_cpp` = 01 인프로세스, `llama_cpp_server` = 02 서버).
즉 여기서 개념을 익히면 메인 앱의 임베딩 엔진을 완전히 이해한 셈이다.
예제 03(텍스트 생성)은 현재 메인 앱에는 없는 영역으로, **"llama.cpp 업그레이드"
로드맵(05_upgrade_path)에서 답변 생성 기능을 추가할 때의 출발점**이 된다.

## 실행 방법

각 스크립트는 사전 준비물이 없으면 정확한 준비 방법을 안내하고 종료한다.

```powershell
# 01) 인프로세스 임베딩
python examples\01_llama_cpp\01_inprocess_embedding.py --model "C:\models\nomic-embed-text-v1.5.Q8_0.gguf"

# 02) 서버 임베딩 (llama-server 를 먼저 기동)
#   llama-server -m C:\models\nomic-embed-text-v1.5.Q8_0.gguf --embedding --port 8080
python examples\01_llama_cpp\02_server_embedding.py

# 03) 인프로세스 텍스트 생성
python examples\01_llama_cpp\03_inprocess_text_generation.py --model "C:\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
```
