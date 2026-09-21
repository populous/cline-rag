"""test_hybrid_search.py -- tokenisation, BM25 and hybrid ranking tests.

These cover the keyword/hybrid retrieval path. Embeddings are replaced by the
deterministic fixture from conftest.py, so no external service is needed.
"""

from __future__ import annotations

import pytest

import rag_core as core


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

def test_tokenize_splits_latin_words_and_lowercases():
    assert core.tokenize("Chunk SIZE 800") == ["chunk", "size", "800"]


def test_tokenize_builds_cjk_bigrams():
    assert core.tokenize("청크크기") == ["청크", "크크", "크기"]


def test_tokenize_keeps_single_cjk_character():
    assert core.tokenize("청") == ["청"]


def test_tokenize_mixes_scripts_and_drops_punctuation():
    tokens = core.tokenize("청크 size=800, !")
    assert "size" in tokens
    assert "800" in tokens
    assert "청크" in tokens
    assert "=" not in tokens
    assert "," not in tokens


def test_tokenize_empty_or_symbol_only_text():
    assert core.tokenize("") == []
    assert core.tokenize("   ,.!? ") == []


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

def test_bm25_no_overlap_scores_zero():
    scores = core.bm25_scores("chunk size", ["completely unrelated", "another topic"])
    assert scores == [0.0, 0.0]


def test_bm25_ranks_matching_document_higher():
    scores = core.bm25_scores(
        "chunk size",
        [
            "Chunk size and overlap recommendation",
            "Deployment notes",
            "Something else entirely",
        ],
    )
    assert scores[0] > 0.0
    assert scores[1] == 0.0          # no shared term -> no score
    assert scores[2] == 0.0


def test_bm25_empty_inputs():
    assert core.bm25_scores("anything", []) == []
    assert core.bm25_scores("", ["doc"]) == [0.0]
    assert core.bm25_scores("!!!", ["doc"]) == [0.0]


def test_bm25_prefers_shorter_document_for_same_term_count():
    scores = core.bm25_scores(
        "chunk", ["chunk", "chunk " + "filler " * 50, "unrelated document here"]
    )
    assert scores[0] > scores[1]


def test_bm25_prefers_higher_term_frequency():
    scores = core.bm25_scores(
        "size", ["size", "size size size", "other alpha", "other beta", "other gamma"]
    )
    assert scores[1] > scores[0]


def test_bm25_handles_korean_query():
    scores = core.bm25_scores(
        "재색인", ["전체 재색인이 필요하다.", "다른 내용입니다.", "세 번째 문서입니다."]
    )
    assert scores[0] > scores[1] == 0.0


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _hit(source: str, chunk: int = 0, text: str = "t", score: float = 1.0) -> dict:
    return {"source": source, "chunk_index": chunk, "text": text, "score": score}


def test_rrf_rewards_agreement_between_rankers():
    vector = [_hit("a.md"), _hit("b.md")]
    keyword = [_hit("b.md"), _hit("c.md")]

    fused = core.reciprocal_rank_fusion([vector, keyword], top_k=3)

    assert [hit["source"] for hit in fused] == ["b.md", "a.md", "c.md"]
    # b.md appears at rank 2 and rank 1 in the two lists
    assert fused[0]["score"] == pytest.approx(1 / 62 + 1 / 61, abs=1e-6)


def test_rrf_deduplicates_the_same_chunk():
    assert len(core.reciprocal_rank_fusion([[_hit("a.md")], [_hit("a.md")]])) == 1


def test_rrf_respects_top_k():
    single = [_hit("%d.md" % index) for index in range(5)]
    assert len(core.reciprocal_rank_fusion([single], top_k=2)) == 2


def test_rrf_empty_inputs():
    assert core.reciprocal_rank_fusion([]) == []
    assert core.reciprocal_rank_fusion([[], []]) == []


# ---------------------------------------------------------------------------
# Keyword search against the store
# ---------------------------------------------------------------------------

def test_keyword_search_finds_exact_terms(seeded_store):
    store, _config = seeded_store
    hits = core.keyword_search(store, "800", top_k=3)
    assert hits
    assert hits[0]["source"].endswith("alpha.md")


def test_keyword_search_handles_korean(seeded_store):
    store, _config = seeded_store
    hits = core.keyword_search(store, "재색인", top_k=3)
    assert hits
    assert "재색인" in hits[0]["text"]


def test_keyword_search_without_match_is_empty(seeded_store):
    store, _config = seeded_store
    assert core.keyword_search(store, "zzzznomatch", top_k=3) == []


def test_keyword_search_sources_filter(seeded_store, tmp_path):
    store, _config = seeded_store
    # BM25Okapi 의 idf = log((N-n+0.5)/(n+0.5)) 는 2문서 코퍼스에서 한쪽에만
    # 있는 단어의 idf 가 정확히 0이 되므로, 의미 있는 점수를 보려면 필터링된
    # 코퍼스에 문서가 3개 이상 있어야 한다. alpha.md 에 청크를 하나 더 넣는다.
    core.upsert_chunks(store, [{
        "source": str(tmp_path / "alpha.md"),
        "chunk_index": 2,
        "text": "권장한다는 표현이 문서 곳곳에 등장한다.",
    }])

    alpha_only = [str(tmp_path / "alpha.md")]
    hits = core.keyword_search(store, "권장한다", top_k=5, sources=alpha_only)
    assert hits
    assert all(hit["source"].endswith("alpha.md") for hit in hits)


def test_fetch_all_documents_returns_everything_without_filter(seeded_store):
    store, _config = seeded_store
    assert len(core.fetch_all_documents(store)) == 3


# ---------------------------------------------------------------------------
# search_documents modes
# ---------------------------------------------------------------------------

def test_keyword_mode_does_not_call_the_embedding_provider(seeded_store, fake_embed):
    store, config = seeded_store
    fake_embed.clear()
    hits = core.search_documents(
        "재색인", mode="keyword", top_k=3, cfg=config,
        db_path=core.resolve_store_path(config),
    )
    assert hits
    assert fake_embed == []


def test_vector_mode_uses_embeddings(seeded_store, fake_embed):
    store, config = seeded_store
    fake_embed.clear()
    hits = core.search_documents(
        "재색인", mode="vector", top_k=3, cfg=config,
        db_path=core.resolve_store_path(config),
    )
    assert hits
    assert fake_embed


def test_hybrid_mode_uses_both_rankers(seeded_store, fake_embed):
    store, config = seeded_store
    fake_embed.clear()
    hits = core.search_documents(
        "재색인", mode="hybrid", top_k=3, cfg=config,
        db_path=core.resolve_store_path(config),
    )
    assert hits
    assert fake_embed
    assert len(hits) <= 3


def test_hybrid_is_one_of_the_advertised_modes():
    assert "hybrid" in core.MODES
    assert set(core.MODES) == {"vector", "keyword", "hybrid"}


def test_unknown_mode_raises_value_error(seeded_store, fake_embed):
    store, config = seeded_store
    with pytest.raises(ValueError):
        core.search_documents(
            "x", mode="banana", cfg=config,
            db_path=core.resolve_store_path(config),
        )


def test_missing_store_raises_file_not_found(tmp_path, fake_embed):
    config = core.load_config()
    config["store"]["path"] = str(tmp_path / "absent_store")
    with pytest.raises(FileNotFoundError):
        core.search_documents("x", mode="keyword", cfg=config)
