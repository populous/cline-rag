"""conftest.py -- pytest 공용 픽스처.

핵심 원칙: 테스트는 **외부 서비스에 의존하지 않는다**.
Ollama/OpenAI 를 부르지 않도록 임베딩을 결정적(deterministic) 가짜 함수로 바꾼다.
덕분에 CI 나 다른 PC 에서도 그대로 통과한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
TESTS_DIR = Path(__file__).resolve().parent

# src(소스), tests(conftest), 프로젝트 루트(config) 를 임포트 경로에 넣는다.
for _path in (TESTS_DIR, SRC_DIR, PROJECT_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import rag_core as core  # noqa: E402

# 테스트용 벡터 차원(작게 유지해 빠르게 돈다)
FAKE_DIM = 8


def fake_vector(text: str) -> list[float]:
    """텍스트에서 결정적으로 8차원 벡터를 만든다(외부 호출 없음).

    같은 텍스트 -> 같은 벡터이므로 코사인 유사도를 검증할 수 있다.
    """
    buckets = [0.0] * FAKE_DIM
    for index, char in enumerate(text):
        buckets[(index + ord(char)) % FAKE_DIM] += 1.0
    if not any(buckets):
        buckets[0] = 1.0
    return buckets


@pytest.fixture
def fake_embed(monkeypatch):
    """core.embed_texts 를 가짜 임베딩으로 교체한다."""
    calls: list[list[str]] = []

    def _embed(texts, cfg=None):
        calls.append(list(texts))
        return [fake_vector(text) for text in texts]

    monkeypatch.setattr(core, "embed_texts", _embed)
    monkeypatch.setattr(core, "embed_batches", lambda texts, cfg=None, batch_size=16,
                        progress=None: [fake_vector(t) for t in texts])
    return calls


@pytest.fixture
def temp_config(tmp_path) -> dict:
    """저장소가 tmp_path 를 가리키는 설정을 만든다."""
    cfg = core.load_config()
    cfg["store"]["path"] = str(tmp_path / "test_store.sqlite3")
    return cfg


@pytest.fixture
def seeded_store(tmp_path):
    """샘플 청크가 들어 있는 저장소를 만들어 (conn, cfg) 를 돌려준다."""
    db_path = tmp_path / "test_store.sqlite3"
    cfg = core.load_config()
    cfg["store"]["path"] = str(db_path)

    rows = [
        {
            "source": str(tmp_path / "alpha.md"),
            "chunk_index": 0,
            "text": "청크 크기는 800자, 겹침은 120자를 권장한다.",
        },
        {
            "source": str(tmp_path / "alpha.md"),
            "chunk_index": 1,
            "text": "임베딩 모델을 바꾸면 전체 재색인이 필요하다.",
        },
        {
            "source": str(tmp_path / "beta.md"),
            "chunk_index": 0,
            "text": "Ollama 는 로컬에서 임베딩을 계산한다.",
        },
    ]
    vectors = [fake_vector(row["text"]) for row in rows]

    conn = core.connect(db_path)
    core.upsert_chunks(conn, rows, vectors, cfg)
    yield conn, cfg
    conn.close()


@pytest.fixture
def mcp_stdin():
    """MCP 서버에 넣을 JSON-RPC 줄들을 만드는 헬퍼."""
    def _build(*messages) -> str:
        return "".join(
            json.dumps(message, ensure_ascii=False) + "\n" for message in messages
        )
    return _build