"""ingest.py -- 문서를 청크로 나눠 임베딩하고 SQLite 저장소에 색인한다.

사용 예(프로젝트 트에서 실행):
    python src/ingest.py                      # docs/ 폴더 전체 색인
    python src/ingest.py docs README.md       # 특정 경로만 색인
    python src/ingest.py --reset              # 저장소를 비우고 새로 색인
    python src/ingest.py --stats              # 색인 현황만 출력
    python src/ingest.py --list               # 색인된 파일 목록 출력
    python src/ingest.py --provider openai    # 임베딩 제공자 임시 변경

CMake/CTest 로 돌릴 때는 PYTHONPATH=src 가 주입된다.
"""

from __future__ import annotations

import argparse
import sys

import rag_core as core

# 프로젝트 루트는 rag_core 가 결정한다(소스는 src/ 에 있음).
PROJECT_DIR = core.PROJECT_DIR


def force_utf8_output() -> None:
    """Pin stdout/stderr to UTF-8 before printing Korean status lines.

    Windows consoles may default to cp1252 or cp949, which cannot encode
    Korean and would raise UnicodeEncodeError (seen on GitHub's runner).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="문서를 임베딩해 SQLite RAG 저장소에 색인합니다."
    )
    parser.add_argument(
        "paths", nargs="*", default=None,
        help="색인할 파일/폴더 (기본값: docs/)",
    )
    parser.add_argument("--config", default=None, help="config.json 경로")
    parser.add_argument("--provider", default=None,
                        help="임베딩 제공자 (ollama | openai)")
    parser.add_argument("--reset", action="store_true",
                        help="색인 전에 저장소를 비운다")
    parser.add_argument("--stats", action="store_true",
                        help="색인 현황만 출력하고 종료(읽기 전용, 다른 플래그 무시)")
    parser.add_argument("--list", action="store_true",
                        help="색인된 파일 목록만 출력(읽기 전용, 다른 플래그 무시)")
    parser.add_argument("--prune", action="store_true",
                        help="더 이상 존재하지 않는 파일의 청크를 제거")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="임베딩 요청 배치 크기 (기본 16)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    force_utf8_output()
    args = parse_args(argv)
    cfg = core.load_config(args.config)
    if args.provider:
        cfg["embedding"]["provider"] = args.provider

    db_path = core.resolve_store_path(cfg, PROJECT_DIR)
    if args.stats or args.list:
        if not db_path.is_file():
            print(f"저장소가 없습니다: {db_path}")
            return 1
        conn = core.connect(db_path)
        try:
            if args.list:
                for item in core.list_sources(conn):
                    print(f"{item['chunks']:5d}  {item['source']}")
            else:
                print(f"저장소: {db_path}")
                for key, value in core.store_stats(conn).items():
                    print(f"  {key}: {value}")
        finally:
            conn.close()
        return 0

    targets = args.paths or [str(PROJECT_DIR / "docs")]
    files = core.iter_document_files(targets)
    if not files:
        print(f"색인할 텍스트 파일이 없습니다. 대상: {targets}")
        return 1

    print(f"임베딩 제공자 : {cfg['embedding']['provider']}")
    print(f"저장소        : {db_path}")
    print(f"대상 파일     : {len(files)}개")

    rows = core.build_chunk_rows(files, cfg)
    if not rows:
        print("생성된 청크가 없습니다(빈 문서).")
        return 1

    conn = core.connect(db_path)
    try:
        if args.reset:
            core.reset_store(conn)
            print("저장소를 비웠습니다.")

        if args.prune:
            known = {row["source"] for row in rows}
            for item in core.list_sources(conn):
                if item["source"] not in known:
                    core.delete_source(conn, item["source"])
                    print(f"제거: {item['source']}")

        texts = [row["text"] for row in rows]
        print(f"청크 {len(texts)}개 임베딩 중...")

        def progress(done: int, total: int) -> None:
            sys.stdout.write(f"\r  진행 {done}/{total}")
            sys.stdout.flush()

        vectors = core.embed_batches(texts, cfg, args.batch_size, progress)
        print()

        written = core.upsert_chunks(conn, rows, vectors, cfg)
        stats = core.store_stats(conn)
        print(f"색인 완료: {written}개 청크 저장")
        print(f"  총 청크   : {stats['chunks']}")
        print(f"  총 파일   : {stats['sources']}")
        print(f"  벡터 차원 : {stats['embedding_dim']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
