"""04_rag_graph_with_llama_cpp.py — 검색 + 생성(RAG)을 잇는 완결형 그래프.

현재 cline-rag 는 검색(R)만 담당하고 생성(G)은 Host(OpenCode/Cline)가 맡는다.
이 예제는 그 두 단계를 하나의 LangGraph 로 묶은 **완결형 RAG 파이프라인**이다:
    START -> retrieve -> generate -> END

* retrieve: 메인 앱의 실제 Chroma 저장소를 읽기 전용으로 열어 검색(rag_core 재사용)
* generate: llama.cpp 로 답변 생성 (미설치 시 안내 문구로 대체해 그래프 흐름을 시연)

실행:
    python examples\\03_langgraph\\04_rag_graph_with_llama_cpp.py --model "C:\\models\\Llama-3.2-1B-Instruct-Q4_K_M.gguf"

검색은 메인 앱 색인(Ollama)이 필요하고, 생성은 llama.cpp(GGUF 모델)가 필요하다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TypedDict

# 메인 앱 src/ 를 import 경로에 추가
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

import rag_core as core  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402


class State(TypedDict):
    question: str
    retrieved: list
    answer: str


# 생성용 LLM 은 그래프 "상태"와 별개로 모듈 전역으로 둔다(상태는 순수 데이터만).
_LLM = None


def _load_llm(model_path: str):
    """llama.cpp 모델을 로드하거나, 없으면 None(안내 대체)을 돌려준다."""
    try:
        from llama_cpp import Llama
    except ImportError:
        return None
    if not Path(model_path).is_file():
        return None
    return Llama(model_path=model_path, n_ctx=2048, n_gpu_layers=0, verbose=False)


def retrieve_node(state: State) -> dict:
    cfg = core.load_config()
    store = core.connect(core.resolve_store_path(cfg), cfg)
    hits = core.search_documents(state["question"], top_k=2, mode="hybrid", cfg=cfg)
    return {"retrieved": hits}


def generate_node(state: State) -> dict:
    context = "\n".join(h["text"][:200] for h in state["retrieved"])
    if _LLM is None:
        return {
            "answer": (
                "[llama.cpp 미설치/모델 부재: 답변 생성 단계를 생략합니다.]\n"
                "검색 결과는 정상 수집되었습니다(위 retrieved)."
            )
        }
    resp = _LLM.create_chat_completion(
        messages=[
            {"role": "system", "content": "다음 문서 내용만 근거로 답하세요:\n" + context},
            {"role": "user", "content": state["question"]},
        ],
        max_tokens=128,
        temperature=0.0,
    )
    return {"answer": resp["choices"][0]["message"]["content"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="검색+생성 RAG 그래프 예제")
    parser.add_argument("--model", default="", help="GGUF 채팅 모델 경로 (선택)")
    args = parser.parse_args(argv)

    # 1) 검색을 위해 저장소가 있는지 확인
    cfg = core.load_config()
    store_path = core.resolve_store_path(cfg)
    if not store_path.is_dir() or not any(store_path.iterdir()):
        print("오류: 색인 저장소가 없습니다:", store_path, file=sys.stderr)
        print("먼저 python src\\ingest.py 로 색인하세요.", file=sys.stderr)
        return 1

    # 2) 생성용 llama.cpp 모델 로드 (선택)
    global _LLM
    _LLM = _load_llm(args.model) if args.model else None
    if _LLM is None and args.model:
        print("경고: llama.cpp 모델을 로드하지 못했습니다. 답변 생성 단계는 안내 문구로 대체됩니다.",
              file=sys.stderr)

    # 3) 그래프 구성
    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    app = graph.compile()

    # 4) 실행
    question = "반차 8회는 연차로 며칠인가?"
    result = app.invoke({"question": question, "retrieved": [], "answer": ""})

    print("[질문]", question)
    print("\n[검색 결과 (retrieved)]")
    for i, h in enumerate(result["retrieved"], start=1):
        print(f"  [{i}] {h['source']}#chunk{h['chunk_index']}")
    print("\n[생성 답변 (answer)]")
    print(" ", result["answer"])

    print("\n완료: 검색+생성 RAG 그래프가 정상 동작했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
