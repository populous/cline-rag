# 05. llama.cpp 업그레이드 로드맵

이 폴더는 "향후 새로운 요구사항은 **llama.cpp 를 업그레이드하는 쪽**으로 개발한다"는
방향을 실천하기 위한 계획과 도구를 담는다. 메인 잡(`src/`)을 훼손하지 않고,
검증이 끝난 뒤에만 반영하는 것이 원칙이다.

## 현재 상태 (v2.2.0)

- 임베딩(검색용 벡터화)은 `ollama`가 기본이고, `llama_cpp`/`llama_cpp_server` 가
  이미 선택 가능하다(`src/embeddings_llama_cpp.py`, PR #9).
- **텍스트 생성(LLM)** 은 cline-rag 가 담당하지 않는다 — Host(OpenCode/Cline)가 맡는다.

## 업그레이드 방향

### 1단계: 벤치마크 (검증)

[`benchmark_embeddings.py`](benchmark_embeddings.py) 로 Ollama 와 `llama_cpp_server`
임베딩의 속도·벡터 일관성을 실제 색인 데이터로 비교한다.

```powershell
# llama-server 를 먼저 기동한 뒤
# llama-server -m C:\models\nomic-embed-text-v1.5.Q8_0.gguf --embedding --port 8080
python examples\05_upgrade_path\benchmark_embeddings.py
```

### 2단계: provider 전환

벤치마크 결과가 만족스러우면, 메인 앱의 임베딩 엔진을 전환한다:

1. `config.json` 의 `embedding.provider` 를 `"llama_cpp_server"` 로 변경
2. `python src\ingest.py --reset` 으로 전체 재색인 (임베딩 공간이 달라지므로 필수)
3. `.\ask.ps1 "질문"` 으로 정상 검색 확인

### 3단계: 생성(Generation) 확장 (후보)

현재 "검색(R)만" 하는 cline-rag 를 "검색+생성(RAG)"으로 확장하고 싶어지면:

- [`../03_langgraph/04_rag_graph_with_llama_cpp.py`](../03_langgraph/04_rag_graph_with_llama_cpp.py)
  가 그 참고 구현이다.
- [`../02_langchain/05_llama_cpp_as_llm_backend.py`](../02_langchain/05_llama_cpp_as_llm_backend.py)
  가 "llama.cpp 를 LangChain LLM 으로 연결"하는 다리다.

### 4단계: 문서/버전 갱신 체크리스트 (메인 잡 반영 시)

- [ ] `ARCHITECTURE.md` 의 "로컬 엔진별 색인/검색 능력 차이" 표 갱신
- [ ] `docs/llama_cpp_provider.md` 의 기본 provider 설명 갱신
- [ ] `CHANGELOG.md` 에 `## [2.3.0]`(또는 해당 버전) 기록 (신규 기능 = minor)
- [ ] `src/rag_server.py` 의 `SERVER_VERSION` 상향
- [ ] pytest 전체 통과 + `ask.ps1`/`smoke_mcp.py` 실제 검증

## 원칙 (메인 잡 보호)

- 여기 있는 모든 실험은 `examples/` 안에서 끝낸다.
- 메인 잡(`src/`, `tests/`, `config.json`) 수정은 **별도 브랜치 + PR + CI 통과** 후에만
  진행한다(기존 릴리스 절차 참고).
