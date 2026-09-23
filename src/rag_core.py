"""rag_core.py -- LangChain + LangGraph 기반 RAG 코어.

v2.0.0부터 다음 컴포넌트를 사용한다:
  * 임베딩       : langchain_ollama.OllamaEmbeddings / langchain_openai.OpenAIEmbeddings
  * 벡터 저장소  : langchain_chroma.Chroma (로컬 디스크에 영속, 별도 서버 불필요)
  * 청킹         : langchain_text_splitters.RecursiveCharacterTextSplitter
  * 키워드 검색  : langchain_community.retrievers.BM25Retriever (+ rank_bm25),
                   CJK(한중일) 문자는 자체 bigram 토크나이저로 전처리한다
  * 검색 오케스트레이션 : langgraph.graph.StateGraph
                   (vector / keyword / hybrid 모드를 노드/조건부 엣지로 분기)

이 파일은 ingest.py(색인기)와 rag_server.py(MCP 서버)가 공유한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph

# --------------------------------------------------------------------------
# 기본 설정
# --------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "embedding": {
        "provider": "ollama",  # "ollama" / "openai" / "llama_cpp" / "llama_cpp_server"
        "ollama": {
            "apiBase": "http://127.0.0.1:11434",
            "model": "nomic-embed-text",
        },
        "openai": {
            "model": "text-embedding-3-small",
            "apiKeyEnv": "OPENAI_API_KEY",
            "apiBase": "https://api.openai.com/v1",
        },
        # llama.cpp 계열 (Ollama 없이 순수 llama.cpp 런타임으로 임베딩).
        # 팩토리/상세는 src/embeddings_llama_cpp.py 와 docs/llama_cpp_provider.md 참고.
        "llama_cpp": {
            "modelPath": "",
            "nCtx": 2048,
            "nGpuLayers": 0,
            "nThreads": None,
        },
        "llama_cpp_server": {
            "apiBase": "http://127.0.0.1:8080/v1",
            "apiKey": "not-needed",
            "model": "local-embedding",
        },
    },
    "store": {
        "path": "rag_store_chroma",   # Chroma persist_directory (디렉터리)
        "collection": "cline_rag",
    },
    "chunking": {
        "size": 800,
        "overlap": 120,
    },
}

# 경로 기준
#   소스 코드는 src/ 에 있고, 설정/저장소 같은 데이터는 프로젝트 루트에 있다.
#   그래서 부모 디렉터리를 프로젝트 루트로 잡는다.
SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent

CONFIG_PATH = PROJECT_DIR / "config.json"

# 색인 대상 텍스트 확장자
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".go", ".rs",
    ".c", ".h", ".cpp", ".hpp", ".sql", ".html", ".css", ".ps1", ".sh",
    ".toml", ".ini", ".cfg", ".log",
}


def deep_merge(base: dict, override: dict) -> dict:
    """override 를 base 에 재귀적으로 병합한 새 dict 를 돌려준다."""
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | os.PathLike | None = None) -> dict:
    """config.json 을 읽어 기본값과 병합한다. 파일이 없으면 기본값을 쓴다."""
    cfg_path = Path(path) if path else CONFIG_PATH
    if cfg_path.is_file():
        with cfg_path.open(encoding="utf-8") as fh:
            return deep_merge(DEFAULT_CONFIG, json.load(fh))
    return json.loads(json.dumps(DEFAULT_CONFIG))


def resolve_store_path(cfg: dict, base_dir: str | os.PathLike | None = None) -> Path:
    """저장소(Chroma persist_directory) 경로를 절대 경로로 만든다.

    상대 경로는 프로젝트 루트 기준으로 해석한다.
    """
    raw = Path(cfg["store"]["path"])
    if raw.is_absolute():
        return raw
    base = Path(base_dir) if base_dir else PROJECT_DIR
    return (base / raw).resolve()


# --------------------------------------------------------------------------
# 임베딩
# --------------------------------------------------------------------------

def build_embeddings(cfg: dict) -> Embeddings:
    """설정된 제공자에 맞는 LangChain Embeddings 인스턴스를 만든다."""
    provider = str(cfg["embedding"]["provider"]).lower()
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        conf = cfg["embedding"]["ollama"]
        return OllamaEmbeddings(model=conf["model"], base_url=conf["apiBase"])
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        conf = cfg["embedding"]["openai"]
        api_key = os.environ.get(conf.get("apiKeyEnv", "OPENAI_API_KEY"), "")
        if not api_key:
            raise RuntimeError(
                f"환경 변수 {conf.get('apiKeyEnv', 'OPENAI_API_KEY')} 가 설정되지 않았습니다."
            )
        return OpenAIEmbeddings(
            model=conf["model"], api_key=api_key, base_url=conf["apiBase"]
        )
    if provider in ("llama_cpp", "llama_cpp_server"):
        from embeddings_llama_cpp import build_llama_cpp_embeddings

        return build_llama_cpp_embeddings(cfg)
    raise ValueError(f"알 수 없는 임베딩 제공자: {provider}")


# --------------------------------------------------------------------------
# 벡터 저장소 (Chroma)
# --------------------------------------------------------------------------

def build_vectorstore(cfg: dict, embeddings: Embeddings,
                      db_path: str | os.PathLike | None = None) -> Chroma:
    """설정을 바탕으로 로컬 영속 Chroma 벡터 저장소를 연다(없으면 생성)."""
    path = Path(db_path) if db_path else resolve_store_path(cfg)
    path.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=cfg["store"].get("collection", "cline_rag"),
        embedding_function=embeddings,
        persist_directory=str(path),
        collection_configuration={"hnsw": {"space": "cosine"}},
    )


def connect(db_path: str | os.PathLike, cfg: dict | None = None,
           embeddings: Embeddings | None = None) -> Chroma:
    """저장소를 연다. embeddings 를 주지 않으면 cfg 기준으로 새로 만든다.

    과거 SQLite 버전과의 이름 호환을 위해 ``connect()`` 이름을 유지한다.
    """
    cfg = cfg or load_config()
    embeddings = embeddings or build_embeddings(cfg)
    return build_vectorstore(cfg, embeddings, db_path)


# --------------------------------------------------------------------------
# 문서 로딩 & 청킹
# --------------------------------------------------------------------------

def read_text_file(path: Path) -> str:
    """인코딩을 바꿔 가며 텍스트 파일을 읽는다."""
    for encoding in ("utf-8", "utf-8-sig", "cp949", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def iter_document_files(targets: list[str | os.PathLike]) -> list[Path]:
    """파일/디렉터리 목록에서 색인할 텍스트 파일들을 모은다."""
    found: list[Path] = []
    for target in targets:
        path = Path(target).expanduser()
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in TEXT_SUFFIXES:
                    found.append(child)
        elif path.is_file():
            found.append(path)
    return found


def build_splitter(cfg: dict | None = None) -> RecursiveCharacterTextSplitter:
    """설정된 크기/겹침으로 RecursiveCharacterTextSplitter 를 만든다."""
    cfg = cfg or load_config()
    chunk_cfg = cfg["chunking"]
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_cfg["size"],
        chunk_overlap=chunk_cfg["overlap"],
        separators=["\n\n", "\n", ". ", "다. ", " ", ""],
    )


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """텍스트를 겹침(overlap)을 가진 청크로 나눈다(RecursiveCharacterTextSplitter 기반).

    과거 SQLite 버전과의 호환을 위해 유지하는 얇은 wrapper 다.
    """
    if size <= 0:
        raise ValueError("chunk size 는 1 이상이어야 합니다.")
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []
    overlap = max(0, min(overlap, size - 1))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", "다. ", " ", ""],
    )
    return [chunk for chunk in splitter.split_text(cleaned) if chunk.strip()]


def build_documents(files: list[Path], cfg: dict | None = None) -> list[Document]:
    """파일들을 청크 단위 LangChain ``Document`` 목록으로 변환한다.

    metadata 는 ``source``(파일 경로 문자열)와 ``chunk_index`` 를 담는다.
    """
    cfg = cfg or load_config()
    splitter = build_splitter(cfg)
    docs: list[Document] = []
    for file_path in files:
        text = read_text_file(file_path)
        cleaned = text.replace("\r\n", "\n").strip()
        if not cleaned:
            continue
        for index, piece in enumerate(splitter.split_text(cleaned)):
            piece = piece.strip()
            if not piece:
                continue
            docs.append(Document(
                page_content=piece,
                metadata={"source": str(file_path), "chunk_index": index},
            ))
    return docs


def build_chunk_rows(files: list[Path], cfg: dict | None = None) -> list[dict]:
    """파일들을 (source, chunk_index, text) 레코드 목록으로 변환한다.

    과거 SQLite 버전과의 호환을 위해 유지하는 얇은 wrapper 다.
    """
    return [
        {
            "source": doc.metadata["source"],
            "chunk_index": doc.metadata["chunk_index"],
            "text": doc.page_content,
        }
        for doc in build_documents(files, cfg)
    ]



# --------------------------------------------------------------------------
# 저장소 CRUD (Chroma 기반)
# --------------------------------------------------------------------------

def _chunk_id(source: str, chunk_index: int) -> str:
    """(source, chunk_index) 를 Chroma 문서 ID로 직렬화한다."""
    return f"{source}::{chunk_index}"


def reset_store(store: Chroma) -> None:
    """저장소의 모든 문서를 지운다(컬렉션을 재생성)."""
    store.reset_collection()


def delete_source(store: Chroma, source: str) -> int:
    """특정 파일(source)에 속한 모든 청크를 지우고 삭제된 개수를 돌려준다."""
    existing = store.get(where={"source": source})
    ids = existing.get("ids") or []
    if ids:
        store.delete(ids=ids)
    return len(ids)


def upsert_documents(store: Chroma, docs: list[Document]) -> int:
    """(source, chunk_index) 기준으로 문서를 저장/갱신한다."""
    if not docs:
        return 0
    ids = [_chunk_id(doc.metadata["source"], doc.metadata["chunk_index"]) for doc in docs]
    # Chroma.add_documents 는 동일 id 가 있으면 upsert(덮어쓰기) 한다.
    store.add_documents(documents=docs, ids=ids)
    return len(docs)


def upsert_chunks(store: Chroma, rows: list[dict],
                  vectors: list[list[float]] | None = None,
                  cfg: dict | None = None) -> int:
    """(source, chunk_index, text) 레코드를 저장한다.

    과거 SQLite 버전과의 호환을 위해 유지하는 얇은 wrapper 다. ``vectors`` 는
    무시되며(Chroma 가 embedding_function 으로 직접 계산한다) 길이 검증만 한다.
    """
    if vectors is not None and rows and len(vectors) != len(rows):
        raise ValueError("rows 와 vectors 의 길이가 일치해야 합니다.")
    docs = [
        Document(
            page_content=row["text"],
            metadata={"source": row["source"], "chunk_index": row["chunk_index"]},
        )
        for row in rows
    ]
    return upsert_documents(store, docs)


def fetch_all_documents(store: Chroma, sources: list[str] | None = None) -> list[Document]:
    """저장소의 모든 문서를 (선택적으로 source 로 필터링해) 돌려준다."""
    where = {"source": {"$in": sources}} if sources else None
    result = store.get(where=where, include=["documents", "metadatas"])
    docs: list[Document] = []
    for doc_id, text, meta in zip(
        result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or []
    ):
        docs.append(Document(page_content=text, metadata=meta or {}, id=doc_id))
    return docs


def store_stats(store: Chroma) -> dict:
    """저장소 현황(총 청크 수, 총 파일 수, 임베딩 제공자)을 돌려준다."""
    result = store.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []
    sources = {meta.get("source") for meta in metadatas if meta}
    provider = None
    embeddings = getattr(store, "_embedding_function", None)
    if embeddings is not None:
        provider = type(embeddings).__name__
    return {
        "chunks": len(metadatas),
        "sources": len(sources),
        "embedding_provider": provider,
    }


def list_sources(store: Chroma) -> list[dict]:
    """색인된 파일 목록과 파일별 청크 수를 돌려준다."""
    result = store.get(include=["metadatas"])
    counts: dict[str, int] = {}
    for meta in result.get("metadatas") or []:
        source = (meta or {}).get("source")
        if source:
            counts[source] = counts.get(source, 0) + 1
    return [
        {"source": source, "chunks": count}
        for source, count in sorted(counts.items())
    ]



# --------------------------------------------------------------------------
# Tokenisation and BM25 keyword search
# --------------------------------------------------------------------------

#: Codepoints at or above this value are treated as CJK (Korean, Chinese,
#: Japanese) and indexed as overlapping character bigrams. Bigrams keep Korean
#: searchable without a morphological analyser or any third-party dependency.
CJK_START = 0x2E80

RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Split text into lowercased Latin/digit words plus CJK bigrams.

    ``BM25Retriever`` 의 ``preprocess_func`` 로 그대로 전달되어 rank_bm25 가
    한국어 등 CJK 텍스트도 형태소 분석기 없이 다룰 수 있게 한다.
    """
    tokens: list[str] = []
    latin: list[str] = []
    cjk: list[str] = []

    def flush_latin() -> None:
        if latin:
            tokens.append("".join(latin))
            latin.clear()

    def flush_cjk() -> None:
        if len(cjk) == 1:
            tokens.append(cjk[0])
        elif cjk:
            tokens.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
        cjk.clear()

    for char in text.lower():
        if ord(char) >= CJK_START and not char.isspace():
            flush_latin()
            cjk.append(char)
        elif char.isalnum():
            flush_cjk()
            latin.append(char)
        else:
            flush_latin()
            flush_cjk()

    flush_latin()
    flush_cjk()
    return tokens


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    """Score every document against the query using Okapi BM25 (rank_bm25).

    Returns one score per document (higher is better); 0.0 means no overlap.
    """
    if not documents:
        return []
    query_terms = tokenize(query)
    if not query_terms:
        return [0.0] * len(documents)

    from rank_bm25 import BM25Okapi

    doc_terms = [tokenize(document) for document in documents]
    if not any(doc_terms):
        return [0.0] * len(documents)

    vectorizer = BM25Okapi(doc_terms)
    scores = vectorizer.get_scores(query_terms)
    return [max(0.0, float(score)) for score in scores]


def build_bm25_retriever(docs: list[Document], top_k: int = 5) -> BM25Retriever | None:
    """저장된 문서들로부터 BM25Retriever 를 만든다(문서가 없으면 None)."""
    if not docs:
        return None
    return BM25Retriever.from_documents(
        docs, k=max(1, top_k), preprocess_func=tokenize
    )



# --------------------------------------------------------------------------
# 검색
# --------------------------------------------------------------------------

def cosine(a: list[float], b: list[float]) -> float:
    """코사인 유사도(순수 파이썬). 하위 호환/유틸리티용으로 유지한다.

    Chroma 검색 자체는 내부적으로 HNSW 인덱스를 쓰지만, 벡터 두 개를 직접
    비교하고 싶을 때(테스트 등) 이 헬퍼를 쓸 수 있다.
    """
    import math

    if len(a) != len(b):
        return 0.0
    dot = norm_a = norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _hit_from_document(doc: Document, score: float) -> dict:
    return {
        "source": doc.metadata.get("source"),
        "chunk_index": doc.metadata.get("chunk_index"),
        "text": doc.page_content,
        "score": round(float(score), 4),
    }


def keyword_search(store: Chroma, query: str, top_k: int = 5,
                   sources: list[str] | None = None) -> list[dict]:
    """BM25 keyword search over the stored chunks."""
    docs = fetch_all_documents(store, sources)
    scores = bm25_scores(query, [doc.page_content for doc in docs])

    hits = [
        _hit_from_document(doc, score)
        for doc, score in zip(docs, scores)
        if score > 0.0
    ]
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[: max(1, top_k)]


def search(store: Chroma, query: str, top_k: int = 5, min_score: float = 0.0,
          sources: list[str] | None = None) -> list[dict]:
    """질의 문자열과 가장 유사한 청크 top_k 를 코사인 유사도로 돌려준다."""
    where = {"source": {"$in": sources}} if sources else None
    results = store.similarity_search_with_relevance_scores(
        query, k=max(1, top_k), filter=where,
    )
    hits: list[dict] = []
    for doc, score in results:
        if score < min_score:
            continue
        hits.append(_hit_from_document(doc, score))
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[: max(1, top_k)]


def reciprocal_rank_fusion(result_lists: list[list[dict]], top_k: int = 5,
                           k: int = RRF_K) -> list[dict]:
    """Merge ranked result lists with Reciprocal Rank Fusion.

    RRF combines rankings instead of raw scores, so the very different scales
    of cosine similarity (0..1) and BM25 (unbounded) do not need calibrating.
    """
    merged: dict[tuple, dict] = {}
    for results in result_lists:
        for rank, hit in enumerate(results, start=1):
            key = (hit["source"], hit["chunk_index"])
            entry = merged.get(key)
            if entry is None:
                entry = {
                    "source": hit["source"],
                    "chunk_index": hit["chunk_index"],
                    "text": hit["text"],
                    "score": 0.0,
                }
                merged[key] = entry
            entry["score"] += 1.0 / (k + rank)

    ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    for entry in ranked:
        entry["score"] = round(entry["score"], 6)
    return ranked[: max(1, top_k)]


def semantic_search(query: str, top_k: int = 5, min_score: float = 0.0,
                    sources: list[str] | None = None,
                    cfg: dict | None = None,
                    db_path: str | os.PathLike | None = None) -> list[dict]:
    """질의 문자열 -> 저장소 검색까지 한 번에 수행한다(코사인 유사도).

    db_path 를 주면 그 저장소를 쓴다. 주지 않으면 cfg 의 store.path 를
    (rag_core.py 위치 기준으로) 해석해 사용한다.
    """
    cfg = cfg or load_config()
    path = Path(db_path) if db_path else resolve_store_path(cfg)
    if not path.is_dir() or not any(path.iterdir()):
        raise FileNotFoundError(
            f"색인 저장소가 없습니다: {path} (먼저 ingest.py 로 색인하세요)"
        )
    store = connect(path, cfg)
    return search(store, query, top_k, min_score, sources)



# --------------------------------------------------------------------------
# LangGraph 기반 검색 오케스트레이션
# --------------------------------------------------------------------------

#: Supported retrieval modes.
MODES = ("vector", "keyword", "hybrid")

#: How many candidates each ranker contributes before fusion.
CANDIDATE_FACTOR = 4


class SearchState(TypedDict, total=False):
    """검색 그래프가 노드 사이에 주고받는 상태."""

    query: str
    mode: str
    top_k: int
    min_score: float
    sources: list[str] | None
    store: Chroma
    vector_hits: list[dict]
    keyword_hits: list[dict]
    results: list[dict]


def _node_retrieve_vector(state: SearchState) -> dict:
    candidates = max(state["top_k"], state["top_k"] * CANDIDATE_FACTOR) \
        if state["mode"] == "hybrid" else state["top_k"]
    hits = search(
        state["store"], state["query"], candidates,
        state["min_score"], state["sources"],
    )
    return {"vector_hits": hits}


def _node_retrieve_keyword(state: SearchState) -> dict:
    candidates = max(state["top_k"], state["top_k"] * CANDIDATE_FACTOR) \
        if state["mode"] == "hybrid" else state["top_k"]
    hits = keyword_search(
        state["store"], state["query"], candidates, state["sources"],
    )
    return {"keyword_hits": hits}


def _node_fuse_hybrid(state: SearchState) -> dict:
    fused = reciprocal_rank_fusion(
        [state.get("vector_hits") or [], state.get("keyword_hits") or []],
        state["top_k"],
    )
    return {"results": fused}


def _node_finalize_vector(state: SearchState) -> dict:
    return {"results": (state.get("vector_hits") or [])[: state["top_k"]]}


def _node_finalize_keyword(state: SearchState) -> dict:
    return {"results": (state.get("keyword_hits") or [])[: state["top_k"]]}


def _route_mode(state: SearchState) -> str:
    return state["mode"]


def build_search_graph():
    """모드(vector/keyword/hybrid)에 따라 분기하는 LangGraph 그래프를 컴파일한다."""
    graph = StateGraph(SearchState)
    graph.add_node("retrieve_vector", _node_retrieve_vector)
    graph.add_node("retrieve_keyword", _node_retrieve_keyword)
    graph.add_node("fuse_hybrid", _node_fuse_hybrid)
    graph.add_node("finalize_vector", _node_finalize_vector)
    graph.add_node("finalize_keyword", _node_finalize_keyword)

    graph.add_conditional_edges(START, _route_mode, {
        "vector": "retrieve_vector",
        "keyword": "retrieve_keyword",
        "hybrid": "retrieve_vector",
    })

    graph.add_edge("retrieve_vector", "finalize_vector")
    graph.add_conditional_edges("finalize_vector", _route_mode, {
        "vector": END,
        "hybrid": "retrieve_keyword",
    })

    graph.add_edge("retrieve_keyword", "finalize_keyword")
    graph.add_conditional_edges("finalize_keyword", _route_mode, {
        "keyword": END,
        "hybrid": "fuse_hybrid",
    })

    graph.add_edge("fuse_hybrid", END)
    return graph.compile()


#: 그래프는 상태가 없으므로(store 는 매 호출마다 state 로 전달됨) 모듈 전역에
#: 한 번만 컴파일해 재사용한다.
_SEARCH_GRAPH = None


def _get_search_graph():
    global _SEARCH_GRAPH
    if _SEARCH_GRAPH is None:
        _SEARCH_GRAPH = build_search_graph()
    return _SEARCH_GRAPH


def search_documents(query: str, top_k: int = 5, min_score: float = 0.0,
                     sources: list[str] | None = None, mode: str = "hybrid",
                     cfg: dict | None = None,
                     db_path: str | os.PathLike | None = None) -> list[dict]:
    """Retrieve chunks for a query via the LangGraph search graph.

    Modes:
      * ``vector``  - cosine similarity over embeddings (semantic)
      * ``keyword`` - BM25 over tokenised text (exact terms, no embedding call)
      * ``hybrid``  - both rankers merged with Reciprocal Rank Fusion (default)

    ``min_score`` only applies to the vector ranker: after fusion the score is
    rank-based, so a cosine threshold no longer has the same meaning.
    """
    cfg = cfg or load_config()
    mode = (mode or "hybrid").lower()
    if mode not in MODES:
        raise ValueError(
            f"unknown search mode: {mode} (expected one of {', '.join(MODES)})"
        )

    path = Path(db_path) if db_path else resolve_store_path(cfg)
    if not path.is_dir() or not any(path.iterdir()):
        raise FileNotFoundError(
            f"색인 저장소가 없습니다: {path} (먼저 ingest.py 로 색인하세요)"
        )

    store = connect(path, cfg)
    graph = _get_search_graph()
    final_state = graph.invoke({
        "query": query,
        "mode": mode,
        "top_k": max(1, top_k),
        "min_score": min_score,
        "sources": sources,
        "store": store,
    })
    return final_state.get("results", [])

    return (base / raw).resolve()
