"""
advanced_rag_graph.py
-----------------------
cline-rag upgrade: graph(control) layer first.
Reuses the existing hybrid(BM25+vector) search from rag_core.search_documents()
as-is, and adds on top of it: (1) a reranking node, (2) LangGraph StateGraph
orchestration, (3) a LangSmith tracing/performance metrics schema.
"""

from __future__ import annotations

import os
import time
from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

try:
    from langsmith import traceable
    from langsmith.run_helpers import get_current_run_tree
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

    def traceable(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorator


class RetrievalMetrics(TypedDict):
    mode: str
    query: str
    raw_hit_count: int
    latency_ms: float
    top_k_requested: int
    min_score: float


class RerankMetrics(TypedDict):
    reranker_model: str
    input_count: int
    output_count: int
    latency_ms: float
    score_before_after: list


class AdvancedRagRunMetrics(TypedDict):
    run_id: str
    retrieval: RetrievalMetrics
    rerank: RerankMetrics
    total_latency_ms: float
    final_hit_count: int


class AdvancedRagState(TypedDict, total=False):
    query: str
    mode: str
    top_k: int
    min_score: float
    sources: list
    raw_hits: list
    reranked_hits: list
    retrieval_metrics: RetrievalMetrics
    rerank_metrics: RerankMetrics
    final_hit_count: int


@traceable(name="hybrid_retrieve", run_type="retriever")
def hybrid_retrieve(state: AdvancedRagState) -> AdvancedRagState:
    import rag_core as core

    t0 = time.perf_counter()
    cfg = core.load_config(None)
    hits = core.search_documents(
        state["query"],
        top_k=state.get("top_k", 5),
        min_score=state.get("min_score", 0.0),
        sources=state.get("sources"),
        mode=state.get("mode", "hybrid"),
        cfg=cfg,
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    metrics: RetrievalMetrics = {
        "mode": state.get("mode", "hybrid"),
        "query": state["query"],
        "raw_hit_count": len(hits),
        "latency_ms": round(latency_ms, 2),
        "top_k_requested": state.get("top_k", 5),
        "min_score": state.get("min_score", 0.0),
    }
    return {"raw_hits": hits, "retrieval_metrics": metrics}


@traceable(name="rerank", run_type="chain")
def rerank(state: AdvancedRagState) -> AdvancedRagState:
    hits = state["raw_hits"]
    t0 = time.perf_counter()

    try:
        from sentence_transformers import CrossEncoder

        model_name = os.environ.get(
            "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        model = CrossEncoder(model_name)

        pairs = [(state["query"], h.get("content", "")) for h in hits]
        rerank_scores = model.predict(pairs) if pairs else []

        scored = list(zip(hits, rerank_scores))
        scored.sort(key=lambda pair: pair[1], reverse=True)

        top_n = state.get("top_k", 5)
        reranked = [dict(h, rerank_score=float(s)) for h, s in scored[:top_n]]
        score_pairs = [
            (float(h.get("score", 0.0)), float(s)) for h, s in scored[:top_n]
        ]
        model_label = model_name

    except ImportError:
        reranked = hits[: state.get("top_k", 5)]
        score_pairs = [
            (float(h.get("score", 0.0)), float(h.get("score", 0.0))) for h in reranked
        ]
        model_label = "none (fallback, sentence-transformers not installed)"

    latency_ms = (time.perf_counter() - t0) * 1000

    metrics: RerankMetrics = {
        "reranker_model": model_label,
        "input_count": len(hits),
        "output_count": len(reranked),
        "latency_ms": round(latency_ms, 2),
        "score_before_after": score_pairs,
    }
    return {"reranked_hits": reranked, "rerank_metrics": metrics, "final_hit_count": len(reranked)}


@traceable(name="emit_metrics", run_type="chain")
def emit_metrics(state: AdvancedRagState) -> AdvancedRagState:
    if LANGSMITH_AVAILABLE:
        run_tree = get_current_run_tree()
        if run_tree is not None:
            run_tree.extra = run_tree.extra or {}
            run_tree.extra["advanced_rag_metrics"] = {
                "retrieval": state.get("retrieval_metrics"),
                "rerank": state.get("rerank_metrics"),
                "final_hit_count": state.get("final_hit_count", 0),
            }
    return {}


def build_advanced_rag_graph():
    graph = StateGraph(AdvancedRagState)

    graph.add_node("hybrid_retrieve", hybrid_retrieve)
    graph.add_node("rerank", rerank)
    graph.add_node("emit_metrics", emit_metrics)

    graph.add_edge(START, "hybrid_retrieve")
    graph.add_edge("hybrid_retrieve", "rerank")
    graph.add_edge("rerank", "emit_metrics")
    graph.add_edge("emit_metrics", END)

    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "cline-rag-advanced")

    app = build_advanced_rag_graph()

    initial_state: AdvancedRagState = {
        "query": "recommended chunk size",
        "mode": "hybrid",
        "top_k": 5,
        "min_score": 0.0,
        "sources": None,
    }

    config = {"configurable": {"thread_id": "advanced-rag-demo"}}

    for event in app.stream(initial_state, config=config):
        print(event)
