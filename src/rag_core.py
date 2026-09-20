"""rag_core.py -- 의존성 없는(zero-dependency) RAG 코어.

표준 라이브러리만 사용한다:
  * 임베딩  : urllib 로 Ollama 또는 OpenAI 임베딩 API 호출
  * 저장소  : sqlite3 (벡터는 JSON 텍스트로 저장)
  * 유사도  : 순수 파이썬 코사인 유사도

이 파일은 ingest.py(색인기)와 rag_server.py(MCP 서버)가 공유한다.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------
# 기본 설정
# --------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "embedding": {
        "provider": "ollama",  # "ollama" 또는 "openai"
        "ollama": {
            "apiBase": "http://127.0.0.1:11434",
            "model": "nomic-embed-text",
        },
        "openai": {
            "model": "text-embedding-3-small",
            "apiKeyEnv": "OPENAI_API_KEY",
            "apiBase": "https://api.openai.com/v1",
        },
    },
    "store": {
        "path": "rag_store.sqlite3",
        "dim": 768,
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
    """저장소 경로를 절대 경로로 만든다(상대 경로는 프로젝트 루트 기준)."""
    raw = Path(cfg["store"]["path"])
    if raw.is_absolute():
        return raw
    base = Path(base_dir) if base_dir else PROJECT_DIR
    return (base / raw).resolve()


# --------------------------------------------------------------------------
# 임베딩
# --------------------------------------------------------------------------

def _post_json(url: str, payload: dict, headers: dict | None = None,
               timeout: int = 120) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"연결 실패 {url}: {exc.reason}") from exc


def embed_ollama(texts: list[str], cfg: dict) -> list[list[float]]:
    """Ollama /api/embed (신형) 후 /api/embeddings (구형) 로 폴백."""
    conf = cfg["embedding"]["ollama"]
    base = conf["apiBase"].rstrip("/")
    model = conf["model"]

    try:
        data = _post_json(f"{base}/api/embed", {"model": model, "input": texts})
        vectors = data.get("embeddings")
        if vectors:
            return [list(map(float, vec)) for vec in vectors]
    except RuntimeError:
        pass  # 구형 엔드포인트로 재시도

    out: list[list[float]] = []
    for text in texts:
        data = _post_json(f"{base}/api/embeddings", {"model": model, "prompt": text})
        vector = data.get("embedding")
        if not vector:
            raise RuntimeError(f"Ollama 가 임베딩을 반환하지 않았습니다: {data}")
        out.append(list(map(float, vector)))
    return out


def embed_openai(texts: list[str], cfg: dict) -> list[list[float]]:
    conf = cfg["embedding"]["openai"]
    api_key = os.environ.get(conf.get("apiKeyEnv", "OPENAI_API_KEY"), "")
    if not api_key:
        raise RuntimeError(
            f"환경 변수 {conf.get('apiKeyEnv', 'OPENAI_API_KEY')} 가 설정되지 않았습니다."
        )
    base = conf["apiBase"].rstrip("/")
    data = _post_json(
        f"{base}/embeddings",
        {"model": conf["model"], "input": texts},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    rows = sorted(data["data"], key=lambda row: row.get("index", 0))
    return [list(map(float, row["embedding"])) for row in rows]


def embed_texts(texts: list[str], cfg: dict) -> list[list[float]]:
    """설정된 제공자로 임베딩을 계산한다."""
    if not texts:
        return []
    provider = str(cfg["embedding"]["provider"]).lower()
    if provider == "ollama":
        return embed_ollama(texts, cfg)
    if provider == "openai":
        return embed_openai(texts, cfg)
    raise ValueError(f"알 수 없는 임베딩 제공자: {provider}")


def embed_batches(texts: list[str], cfg: dict, batch_size: int = 16,
                  progress=None) -> list[list[float]]:
    """임베딩을 배치 단위로 계산한다(대량 문서용)."""
    vectors: list[list[float]] = []
    total = len(texts)
    for start in range(0, total, batch_size):
        batch = texts[start:start + batch_size]
        vectors.extend(embed_texts(batch, cfg))
        if progress:
            progress(min(start + batch_size, total), total)
    return vectors


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


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """문단 경계를 존중하며 겹침(overlap)을 가진 청크로 나눈다."""
    if size <= 0:
        raise ValueError("chunk size 는 1 이상이어야 합니다.")
    overlap = max(0, min(overlap, size - 1))
    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + size, length)
        if end < length:
            window_start = start + max(size // 2, 1)
            best = -1
            for marker in ("\n\n", "\n", ". ", "다. "):
                pos = cleaned.rfind(marker, window_start, end)
                if pos > best:
                    best = pos + len(marker)
            if best > start:
                end = best
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunk_rows(files: list[Path], cfg: dict | None = None) -> list[dict]:
    """파일들을 (source, chunk_index, text) 레코드 목록으로 변환한다."""
    cfg = cfg or load_config()
    chunk_cfg = cfg["chunking"]
    rows: list[dict] = []
    for file_path in files:
        text = read_text_file(file_path)
        for index, piece in enumerate(
            chunk_text(text, chunk_cfg["size"], chunk_cfg["overlap"])
        ):
            rows.append({
                "source": str(file_path),
                "chunk_index": index,
                "text": piece,
            })
    return rows


# --------------------------------------------------------------------------
# SQLite 벡터 저장소
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,
    chunk_index INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    embedding   TEXT    NOT NULL,
    dim         INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(db_path: str | os.PathLike) -> sqlite3.Connection:
    """저장소를 열고 스키마를 준비한다."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def reset_store(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM chunks")
    conn.commit()


def delete_source(conn: sqlite3.Connection, source: str) -> int:
    cur = conn.execute("DELETE FROM chunks WHERE source = ?", (source,))
    conn.commit()
    return cur.rowcount


def upsert_chunks(conn: sqlite3.Connection, rows: list[dict],
                  vectors: list[list[float]], cfg: dict | None = None) -> int:
    """(source, chunk_index) 기준으로 청크와 벡터를 저장/갱신한다."""
    if len(rows) != len(vectors):
        raise ValueError("청크 수와 벡터 수가 다릅니다.")
    cfg = cfg or load_config()
    payload = [
        (
            row["source"],
            row["chunk_index"],
            row["text"],
            json.dumps([round(float(x), 6) for x in vector]),
            len(vector),
        )
        for row, vector in zip(rows, vectors)
    ]
    conn.executemany(
        """
        INSERT INTO chunks(source, chunk_index, text, embedding, dim)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(source, chunk_index) DO UPDATE SET
            text = excluded.text,
            embedding = excluded.embedding,
            dim = excluded.dim,
            created_at = CURRENT_TIMESTAMP
        """,
        payload,
    )
    conn.commit()
    if vectors:
        set_meta(conn, "embedding_dim", len(vectors[0]))
        set_meta(conn, "embedding_provider", cfg["embedding"]["provider"])
    return len(payload)


def store_stats(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS chunks, COUNT(DISTINCT source) AS sources FROM chunks"
    ).fetchone()
    return {
        "chunks": row["chunks"],
        "sources": row["sources"],
        "embedding_dim": get_meta(conn, "embedding_dim"),
        "embedding_provider": get_meta(conn, "embedding_provider"),
    }


def list_sources(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT source, COUNT(*) AS chunks FROM chunks "
        "GROUP BY source ORDER BY source"
    ).fetchall()
    return [{"source": r["source"], "chunks": r["chunks"]} for r in rows]


# --------------------------------------------------------------------------
# 검색
# --------------------------------------------------------------------------

def cosine(a: list[float], b: list[float]) -> float:
    """코사인 유사도(순수 파이썬, 의존성 없음)."""
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


def search(conn: sqlite3.Connection, query_vector: list[float],
           top_k: int = 5, min_score: float = 0.0,
           sources: list[str] | None = None) -> list[dict]:
    """질의 벡터와 가장 유사한 청크 top_k 를 돌려준다."""
    sql = "SELECT source, chunk_index, text, embedding FROM chunks"
    params: list = []
    if sources:
        placeholders = ",".join("?" for _ in sources)
        sql += f" WHERE source IN ({placeholders})"
        params.extend(sources)

    scored: list[dict] = []
    for row in conn.execute(sql, params):
        score = cosine(query_vector, json.loads(row["embedding"]))
        if score < min_score:
            continue
        scored.append({
            "source": row["source"],
            "chunk_index": row["chunk_index"],
            "text": row["text"],
            "score": round(score, 4),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, top_k)]


def semantic_search(query: str, top_k: int = 5, min_score: float = 0.0,
                    sources: list[str] | None = None,
                    cfg: dict | None = None,
                    db_path: str | os.PathLike | None = None) -> list[dict]:
    """질의 문자열 -> 임베딩 -> 저장소 검색까지 한 번에 수행한다.

    db_path 를 주면 그 저장소를 쓴다. 주지 않으면 cfg 의 store.path 를
    (rag_core.py 위치 기준으로) 해석해 사용한다.
    """
    cfg = cfg or load_config()
    path = Path(db_path) if db_path else resolve_store_path(cfg)
    if not path.is_file():
        raise FileNotFoundError(
            f"색인 저장소가 없습니다: {path} (먼저 ingest.py 로 색인하세요)"
        )
    query_vector = embed_texts([query], cfg)[0]
    conn = connect(path)
    try:
        return search(conn, query_vector, top_k, min_score, sources)
    finally:
        conn.close()
