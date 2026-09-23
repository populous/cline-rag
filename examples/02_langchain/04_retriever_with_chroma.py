"""04_retriever_with_chroma.py — 메인 앱의 Chroma 저장소를 리트리버로 재사용.

cline-rag 의 실제 벡터 저장소(rag_store_chroma)를 "읽기 전용"으로 열어서
LangChain 리트리버로 쓰는 법을 보여준다. 저장소를 수정하지 않으며, 조회만 한다.

두 가지 리트리버를 시연한다:
    * BM25Retriever   — 키워드 기반. 임베딩이 필요 없어 오프라인으로 동작.
    * Chroma as_retriever — 벡터 기반. 질의 임베딩에 Ollama 가 필요.

사전 준비:
    python src\\ingest.py   # 메인 앱 색인 (색인이 없으면 안내 후 종료)

실행:
    python examples\\02_langchain\\04_retriever_with_chroma.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 메인 앱의 src/ 를 import 경로에 추가 (examples 는 메인 앱과 별도 폴더이므로)
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC_DIR))

import rag_core as core  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    cfg = core.load_config()
    store_path = core.resolve_store_path(cfg)

    # 1) 저장소 존재 여부 확인 (없거나 비어 있으면 안내 후 종료)
    if not store_path.is_dir() or not any(store_path.iterdir()):
        print("오류: 색인 저장소가 없습니다:", store_path, file=sys.stderr)
        print("먼저 메인 앱을 색인하세요:\n  python src\\ingest.py", file=sys.stderr)
        return 1

    try:
        store = core.connect(store_path, cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"오류: 저장소를 열 수 없습니다: {exc}", file=sys.stderr)
        print("임베딩 제공자(Ollama)가 실행 중인지, 색인이 정상인지 확인하세요.", file=sys.stderr)
        return 1

    query = "반차는 연차로 어떻게 환산되나?"

    # 2) BM25Retriever — 키워드 검색 (임베딩 없이 동작)
    print("[1/2] BM25Retriever (키워드 기반, 오프라인)")
    try:
        docs = core.fetch_all_documents(store)
        if not docs:
            print("      색인된 문서가 없습니다. python src\\ingest.py 로 색인하세요.")
            return 1
        bm25 = core.build_bm25_retriever(docs, top_k=2)
        for i, doc in enumerate(bm25.invoke(query), start=1):
            src = doc.metadata.get("source", "?")
            print(f"      [{i}] {src}  ({len(doc.page_content)}자)")
    except Exception as exc:  # noqa: BLE001
        print(f"      BM25 리트리버 실패: {exc}")

    # 3) Chroma as_retriever — 벡터 검색 (질의 임베딩에 Ollama 필요)
    print("\n[2/2] Chroma as_retriever (벡터 기반, Ollama 필요)")
    try:
        retriever = store.as_retriever(search_kwargs={"k": 2})
        for i, doc in enumerate(retriever.invoke(query), start=1):
            src = doc.metadata.get("source", "?")
            preview = doc.page_content.strip().splitlines()[0][:50]
            print(f"      [{i}] {src}: {preview}")
    except Exception as exc:  # noqa: BLE001
        print("      벡터 검색 실패(아마 Ollama 미실행). 안내:", file=sys.stderr)
        print(f"        {exc}", file=sys.stderr)
        print("      Ollama 실행 확인: ollama serve / ollama list", file=sys.stderr)

    print("\n완료: 메인 앱 저장소를 리트리버로 재사용했습니다(읽기 전용).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
