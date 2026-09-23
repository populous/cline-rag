"""test_advanced_rag_graph.py -- advanced_rag_graph 의 노드 단위 테스트.

원칙(외부 서비스 불필요):
    * hybrid_retrieve 는 conftest 의 fake_embed/seeded_store 를 재사용한다.
    * rerank 는 가짜 sentence_transformers 를 주입해 "text 필드" 사용을 검증하고,
      미설치 폴백 경로도 결정적으로 검증한다.
    * emit_metrics 는 langsmith 비활성 상태에서 아무것도 하지 않는지 확인한다.
"""

from __future__ import annotations

import builtins
import sys
import types

import pytest

import rag_core as core
import advanced_rag_graph as agg


def _sample_hits() -> list[dict]:
    return [
        {"source": "a.md", "chunk_index": 0, "text": "첫 번째 문서 텍스트", "score": 0.3},
        {"source": "b.md", "chunk_index": 0, "text": "두 번째 문서 텍스트", "score": 0.7},
    ]


# ---------------------------------------------------------------------------
# hybrid_retrieve
# ---------------------------------------------------------------------------

def test_hybrid_retrieve_returns_hits_with_text_field(seeded_store, fake_embed, monkeypatch):
    store, cfg = seeded_store
    # hybrid_retrieve 는 내부에서 core.load_config(None) 을 부르므로,
    # seeded_store 의 tmp 경로를 가리키도록 고정한다.
    monkeypatch.setattr(core, "load_config", lambda path=None: cfg)

    state = {
        "query": "청크 크기",
        "mode": "hybrid",
        "top_k": 2,
        "min_score": 0.0,
        "sources": None,
    }
    result = agg.hybrid_retrieve(state)

    assert "raw_hits" in result
    assert len(result["raw_hits"]) > 0
    # 실제 hit 딕셔너리의 필드명은 "text" 이며 "content" 는 없다.
    for hit in result["raw_hits"]:
        assert "text" in hit
        assert "content" not in hit

    metrics = result["retrieval_metrics"]
    assert metrics["raw_hit_count"] == len(result["raw_hits"])
    assert metrics["mode"] == "hybrid"
    assert metrics["query"] == "청크 크기"


# ---------------------------------------------------------------------------
# rerank: text 필드 사용 검증 (가짜 sentence_transformers 주입)
# ---------------------------------------------------------------------------

def test_rerank_uses_text_field_for_cross_encoder_pairs(monkeypatch):
    captured: dict = {}

    fake_st = types.ModuleType("sentence_transformers")

    class FakeCrossEncoder:
        def __init__(self, model_name):
            self.model_name = model_name

        def predict(self, pairs):
            captured["pairs"] = pairs
            captured["model_name"] = self.model_name
            return [0.95, 0.4]

    fake_st.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)

    state = {"query": "질문", "raw_hits": _sample_hits(), "top_k": 2}
    result = agg.rerank(state)

    # 교차 인코더가 받은 쌍에 "text" 필드의 실제 본문이 들어가야 한다(버그 수정 검증).
    assert captured["pairs"] == [
        ("질문", "첫 번째 문서 텍스트"),
        ("질문", "두 번째 문서 텍스트"),
    ]
    assert captured["model_name"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # 리랭킹 점수(내림차순)가 붙었는지
    assert [h["rerank_score"] for h in result["reranked_hits"]] == [0.95, 0.4]
    assert result["reranked_hits"][0]["text"] == "첫 번째 문서 텍스트"
    assert result["final_hit_count"] == 2
    assert result["rerank_metrics"]["input_count"] == 2
    assert result["rerank_metrics"]["output_count"] == 2


# ---------------------------------------------------------------------------
# rerank: sentence-transformers 미설치 폴백 경로
# ---------------------------------------------------------------------------

def test_rerank_fallback_preserves_order_when_not_installed(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    hits = _sample_hits()
    state = {"query": "질문", "raw_hits": hits, "top_k": 2}
    result = agg.rerank(state)

    # 폴백은 원래 순위 그대로 통과한다.
    assert result["reranked_hits"] == hits
    assert result["rerank_metrics"]["reranker_model"].startswith("none")
    assert result["final_hit_count"] == 2


# ---------------------------------------------------------------------------
# emit_metrics
# ---------------------------------------------------------------------------

def test_emit_metrics_is_noop_when_langsmith_unavailable(monkeypatch):
    monkeypatch.setattr(agg, "LANGSMITH_AVAILABLE", False)
    state = {
        "retrieval_metrics": {"mode": "hybrid"},
        "rerank_metrics": {"reranker_model": "none"},
        "final_hit_count": 2,
    }
    assert agg.emit_metrics(state) == {}


# ---------------------------------------------------------------------------
# 그래프 컴파일
# ---------------------------------------------------------------------------

def test_build_advanced_rag_graph_compiles():
    app = agg.build_advanced_rag_graph()
    assert app is not None
