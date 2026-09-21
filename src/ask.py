"""ask.py -- 터미널에서 바로 질문하고 검색 결과를 보는 CLI.

MCP/JSON-RPC 를 몰라도, 파이프/리다이렉션 인코딩 문제 없이 곧바로 검색을
확인할 수 있게 만든 도구다. 질문은 커맨드라인 인자로 받는다(파이프로 흘려
보내지 않으므로 Windows 콘솔 코드페이지에 영향을 받지 않는다).

사용 예(프로젝트 루트에서 실행):
    python src\\ask.py "연차는 반차 단위로도 신청할 수 있니?"
    python src\\ask.py --top-k 3 --mode vector "청크 크기는 얼마가 적당한가?"
    python src\\ask.py --json "청크 크기" > result.json   # 스크립트 연동용

내부적으로 rag_server.py 의 tool_search_docs() 와 동일한 코드 경로
(rag_core.search_documents)를 그대로 호출하므로, 여기서 본 결과는 Cline 이
search_docs 도구를 호출했을 때와 100% 동일하다.
"""

from __future__ import annotations

import argparse
import json
import sys

import rag_core as core


def force_utf8_output() -> None:
    """Windows 콘솔의 cp949/cp1252 코드페이지와 무관하게 UTF-8로 출력한다."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="색인된 문서에 바로 질문하고 검색 결과를 확인합니다."
    )
    parser.add_argument("query", help="검색할 질문이나 키워드")
    parser.add_argument("--top-k", type=int, default=3, help="가져올 청크 수 (기본 3)")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="코사인 유사도 하한 (vector 모드에서만 적용, 기본 0.0)")
    parser.add_argument("--mode", choices=list(core.MODES), default="hybrid",
                        help="hybrid(기본)|vector|keyword")
    parser.add_argument("--sources", nargs="*", default=None,
                        help="이 파일 경로들만 검색한다(생략하면 전체)")
    parser.add_argument("--config", default=None, help="config.json 경로")
    parser.add_argument("--json", action="store_true",
                        help="사람이 읽는 형식 대신 JSON 으로 출력한다")
    return parser.parse_args(argv)


def format_human(query: str, mode: str, hits: list[dict]) -> str:
    if not hits:
        return f"'{query}' 에 대한 검색 결과가 없습니다. (mode={mode})"
    lines = [f"'{query}' [{mode}] 검색 결과 {len(hits)}건", ""]
    for rank, hit in enumerate(hits, start=1):
        lines.append(f"[{rank}] score={hit['score']} | {hit['source']}#chunk{hit['chunk_index']}")
        lines.append(hit["text"])
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    force_utf8_output()
    args = parse_args(argv)
    cfg = core.load_config(args.config)

    try:
        hits = core.search_documents(
            args.query, top_k=args.top_k, min_score=args.min_score,
            sources=args.sources, mode=args.mode, cfg=cfg,
        )
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"query": args.query, "mode": args.mode, "hits": hits},
                         ensure_ascii=False, indent=2))
    else:
        print(format_human(args.query, args.mode, hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
