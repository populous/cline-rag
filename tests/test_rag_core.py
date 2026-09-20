"""test_rag_core.py -- RAG 코어 단위 테스트 (외부 서비스 불필요).

검증 대상:
  * 설정 병합/경로 해석
  * 스트 청킹(경계, 겹침, 예외)
  * 코사인 유사도
  * SQLite 벡터 저장소 CRUD
  * 검색 순위 / top_k / min_score / sources 필터
"""

from __future__ import annotations

import json

import pytest

import rag_core as core
from conftest import fake_vector


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

def test_load_config_defaults_when_file_missing(tmp_path):
    cfg = core.load_config(tmp_path / "no_such_config.json")
    assert cfg["embedding"]["provider"] == "ollama"
    assert cfg["chunking"]["size"] == 800
    assert cfg["chunking"]["overlap"] == 120


def test_load_config_merges_partial_override(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"chunking": {"size": 100}, "embedding": {"provider": "openai"}}),
        encoding="utf-8",
    )
    cfg = core.load_config(path)
    assert cfg["chunking"]["size"] == 100
    assert cfg["chunking"]["overlap"] == 120          # 기본값 유지
    assert cfg["embedding"]["provider"] == "openai"
    assert cfg["store"]["path"] == "rag_store.sqlite3"  # 기본값 유지


def test_deep_merge_does_not_mutate_base():
    base = {"a": {"b": 1}, "c": 2}
    merged = core.deep_merge(base, {"a": {"b": 9}})
    assert merged["a"]["b"] == 9
    assert base["a"]["b"] == 1        # 원본 보존


def test_resolve_store_path_relative_and_absolute(tmp_path):
    relative = core.resolve_store_path({"store": {"path": "a/b.sqlite3"}}, tmp_path)
    assert relative == (tmp_path / "a" / "b.sqlite3").resolve()

    absolute = core.resolve_store_path({"store": {"path": str(tmp_path / "x.sqlite3")}})
    assert absolute == tmp_path / "x.sqlite3"


# ---------------------------------------------------------------------------
# 청킹
# ---------------------------------------------------------------------------

def test_chunk_text_splits_with_overlap():
    """100자를 size=40/overlap=10 로 나누면 3개(40+40+40)가 전체를 덮는다."""
    chunks = core.chunk_text("A" * 100, size=40, overlap=10)
    assert len(chunks) == 3
    assert all(len(chunk) == 40 for chunk in chunks)
    # 이웃한 청크는 10자를 공유한다(겹침 설계 확인)
    assert chunks[0][-10:] == chunks[1][:10]
    assert chunks[1][-10:] == chunks[2][:10]


def test_chunk_text_without_overlap_advances_fully():
    chunks = core.chunk_text("B" * 90, size=30, overlap=0)
    assert len(chunks) == 3
    assert all(len(chunk) == 30 for chunk in chunks)


def test_chunk_text_short_text_is_single_chunk():
    assert core.chunk_text("짧은 문서", size=800, overlap=120) == ["짧은 문서"]


def test_chunk_text_empty_returns_empty_list():
    assert core.chunk_text("", size=100, overlap=10) == []
    assert core.chunk_text("   \n\n  ", size=100, overlap=10) == []


def test_chunk_text_invalid_size_raises():
    with pytest.raises(ValueError):
        core.chunk_text("abc", size=0, overlap=0)


def test_chunk_text_prefers_paragraph_boundary():
    text = ("가" * 60) + "\n\n" + ("나" * 60)
    chunks = core.chunk_text(text, size=80, overlap=10)
    assert chunks[0].endswith("가")      # 문단 경계에서 잘림
    assert not chunks[0].startswith("나")


def test_chunk_text_covers_whole_document():
    text = "문장입니다. " * 60
    chunks = core.chunk_text(text, size=100, overlap=20)
    assert chunks[0].startswith("문장입니다.")
    assert chunks[-1].endswith("문장입니다.")


# ---------------------------------------------------------------------------
# 코사인 유사도
# ---------------------------------------------------------------------------

def test_cosine_identical_is_one():
    vector = [1.0, 2.0, 3.0]
    assert core.cosine(vector, vector) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert core.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_dimension_mismatch_returns_zero():
    assert core.cosine([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_cosine_zero_vector_returns_zero():
    assert core.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_opposite_is_minus_one():
    assert core.cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# 저장소 (SQLite)
# ---------------------------------------------------------------------------

def test_connect_creates_schema(tmp_path):
    conn = core.connect(tmp_path / "s.sqlite3")
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert {"chunks", "meta"} <= tables


def test_connect_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "deep" / "s.sqlite3"
    conn = core.connect(db_path)
    conn.close()
    assert db_path.is_file()


def test_upsert_then_stats(tmp_path):
    conn = core.connect(tmp_path / "s.sqlite3")
    try:
        rows = [{"source": "a.md", "chunk_index": 0, "text": "hello"}]
        assert core.upsert_chunks(conn, rows, [[1.0, 0.0]], core.load_config()) == 1
        stats = core.store_stats(conn)
    finally:
        conn.close()
    assert stats["chunks"] == 1
    assert stats["sources"] == 1
    assert stats["embedding_dim"] == 2


def test_upsert_overwrites_same_source_and_index(tmp_path):
    conn = core.connect(tmp_path / "s.sqlite3")
    try:
        first = [{"source": "a.md", "chunk_index": 0, "text": "old"}]
        core.upsert_chunks(conn, first, [[1.0, 0.0]], core.load_config())
        second = [{"source": "a.md", "chunk_index": 0, "text": "new"}]
        core.upsert_chunks(conn, second, [[0.0, 1.0]], core.load_config())

        assert core.store_stats(conn)["chunks"] == 1   # 중복 저장 안 됨
        stored = conn.execute("SELECT text FROM chunks").fetchone()["text"]
    finally:
        conn.close()
    assert stored == "new"


def test_upsert_length_mismatch_raises(tmp_path):
    conn = core.connect(tmp_path / "s.sqlite3")
    try:
        rows = [{"source": "a.md", "chunk_index": 0, "text": "x"}]
        with pytest.raises(ValueError):
            core.upsert_chunks(conn, rows, [], core.load_config())
    finally:
        conn.close()


def test_delete_source_and_reset_store_seeded(seeded_store):
    conn, _cfg = seeded_store
    assert len(core.list_sources(conn)) == 2

    removed = core.delete_source(conn, str(conn.execute(
        "SELECT source FROM chunks LIMIT 1").fetchone()["source"]))
    assert removed == 2                             # alpha.md 청크 2개
    assert len(core.list_sources(conn)) == 1

    core.reset_store(conn)
    assert core.store_stats(conn)["chunks"] == 0


def test_meta_roundtrip(seeded_store):
    conn, _cfg = seeded_store
    core.set_meta(conn, "flag", {"nested": [1, 2]})
    assert core.get_meta(conn, "flag") == {"nested": [1, 2]}
    assert core.get_meta(conn, "missing", "fallback") == "fallback"


def test_list_sources_counts(seeded_store):
    conn, _cfg = seeded_store
    items = {item["source"]: item["chunks"] for item in core.list_sources(conn)}
    assert sorted(items.values()) == [1, 2]


# ---------------------------------------------------------------------------
# 검색
# ---------------------------------------------------------------------------

def test_search_ranks_most_similar_first(seeded_store):
    conn, _cfg = seeded_store
    query = fake_vector("임베딩 모델을 바꾸면 전체 재색인이 필요하다.")
    hits = core.search(conn, query, top_k=3)

    assert hits[0]["chunk_index"] == 1
    assert hits[0]["source"].endswith("alpha.md")
    assert hits[0]["score"] == pytest.approx(1.0, abs=1e-3)


def test_search_respects_top_k(seeded_store):
    conn, _cfg = seeded_store
    hits = core.search(conn, fake_vector("청크"), top_k=2)
    assert len(hits) == 2


def test_search_min_score_filters(seeded_store):
    conn, _cfg = seeded_store
    hits = core.search(conn, fake_vector("청크"), top_k=5, min_score=0.99)
    assert all(hit["score"] >= 0.99 for hit in hits)
    assert len(hits) <= 1


def test_search_sources_filter(seeded_store):
    conn, _cfg = seeded_store
    only_beta = [str(row["source"]) for row in conn.execute(
        "SELECT DISTINCT source FROM chunks WHERE source LIKE '%beta.md'")]
    hits = core.search(conn, fake_vector("Ollama"), top_k=5, sources=only_beta)
    assert len(hits) == 1
    assert hits[0]["source"].endswith("beta.md")


def test_semantic_search_uses_embeddings(seeded_store, fake_embed, monkeypatch,
                                          tmp_path):
    conn, cfg = seeded_store
    monkeypatch.setattr(core, "resolve_store_path", lambda *a, **k: tmp_path / "test_store.sqlite3")

    hits = core.semantic_search("임베딩 모델 교체", top_k=2, cfg=cfg)
    assert hits
    assert fake_embed                               # 임베딩 호출 기록 존재
    assert hits[0]["score"] >= hits[-1]["score"]    # 내림차순 정렬


def test_semantic_search_missing_store_raises(tmp_path, fake_embed):
    cfg = core.load_config()
    cfg["store"]["path"] = str(tmp_path / "absent.sqlite3")
    with pytest.raises(FileNotFoundError):
        core.semantic_search("무엇이든", cfg=cfg)