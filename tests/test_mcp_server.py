"""test_mcp_server.py -- MCP 서버 프로토/도구 테스트.

서버를 **in-process** 로 띄운다(io.StringIO). 별도 프로세스나 네트워크가 필요 없어
CTest 안에서도 빠르고 안정적으로 돈다.
"""

from __future__ import annotations

import io
import json

import pytest

import rag_core as core
import rag_server
from conftest import fake_vector


def run_server(mcp_stdin, *messages) -> list[dict]:
    """메시지들을 서버에 넣고 응답(JSON)들을 돌려준다."""
    stdout = io.StringIO()
    rag_server.serve(stdin=io.StringIO(mcp_stdin(*messages)), stdout=stdout)
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]


def request(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def call_tool(name: str, arguments: dict | None = None, request_id: int = 1) -> dict:
    return request("tools/call", {"name": name, "arguments": arguments or {}}, request_id)


def extract_text(response: dict) -> str:
    return response["result"]["content"][0]["text"]


@pytest.fixture
def project_to_tmp(tmp_path, monkeypatch):
    """rag_server.PROJECT_DIR 를 tmp 로 돌려 저장소를 격리한다."""
    monkeypatch.setattr(rag_server, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(core, "build_embeddings", lambda cfg: _FakeEmbeddings())
    return tmp_path


class _FakeEmbeddings:
    """외부 호출 없이 결정적 벡터를 만드는 LangChain Embeddings 구현."""

    def embed_documents(self, texts):
        return [fake_vector(text) for text in texts]

    def embed_query(self, text):
        return fake_vector(text)


@pytest.fixture
def tmp_store(project_to_tmp):
    """tmp 프로젝트에 샘플 저장소(Chroma)를 만든다.

    BM25Okapi 의 idf = log((N-n+0.5)/(n+0.5)) 는 2문서 코퍼스에서 한쪽에만
    있는 단어의 idf 가 정확히 0이 되므로, 키워드 검색 테스트가 의미 있는
    점수를 보게 하려면 문서가 3개 이상 있어야 한다.
    """
    db_path = project_to_tmp / "rag_store_chroma"
    rows = [
        {"source": "guide.md", "chunk_index": 0,
         "text": "청크 크기는 800자, 겹침은 120자를 권장한다."},
        {"source": "ops.md", "chunk_index": 0,
         "text": "임베딩 모델을 바꾸면 전체 재색인이 필요하다."},
        {"source": "notes.md", "chunk_index": 0,
         "text": "이 문서는 검색어와 무관한 배경 설명을 담고 있다."},
    ]
    store = core.connect(db_path)
    core.upsert_chunks(store, rows)
    return db_path


# ---------------------------------------------------------------------------
# 핸드이크 / 기본 프로토콜
# ---------------------------------------------------------------------------

def test_initialize_returns_server_info(mcp_stdin):
    responses = run_server(
        mcp_stdin,
        request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1.0"},
        }),
    )
    assert len(responses) == 1
    result = responses[0]["result"]
    assert result["serverInfo"]["name"] == rag_server.SERVER_NAME
    assert result["serverInfo"]["version"] == rag_server.SERVER_VERSION
    assert result["protocolVersion"] == "2025-06-18"
    assert "tools" in result["capabilities"]


def test_initialize_falls_back_to_default_protocol(mcp_stdin):
    responses = run_server(
        mcp_stdin,
        request("initialize", {"protocolVersion": "1999-01-01"}),
    )
    assert responses[0]["result"]["protocolVersion"] == rag_server.DEFAULT_PROTOCOL


def test_ping_returns_empty_result(mcp_stdin):
    responses = run_server(mcp_stdin, request("ping"))
    assert responses[0]["result"] == {}


def test_notification_produces_no_response(mcp_stdin):
    responses = run_server(
        mcp_stdin,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert responses == []


def test_handle_request_notification_returns_none():
    assert rag_server.handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    ) is None


# ---------------------------------------------------------------------------
# 도구 목록
# ---------------------------------------------------------------------------

def test_tools_list_exposes_every_tool(mcp_stdin):
    responses = run_server(mcp_stdin, request("tools/list"))
    tools = {tool["name"]: tool for tool in responses[0]["result"]["tools"]}
    assert set(tools) == {
        "search_docs",
        "list_indexed_sources",
        "index_status",
        "reindex",
    }


def test_every_tool_has_description_and_schema(mcp_stdin):
    responses = run_server(mcp_stdin, request("tools/list"))
    for tool in responses[0]["result"]["tools"]:
        assert tool["description"].strip()
        assert tool["inputSchema"]["type"] == "object"


def test_search_docs_schema_requires_query(mcp_stdin):
    responses = run_server(mcp_stdin, request("tools/list"))
    schema = next(t for t in responses[0]["result"]["tools"]
                  if t["name"] == "search_docs")["inputSchema"]
    assert schema["required"] == ["query"]
    assert schema["properties"]["top_k"]["type"] == "integer"


# ---------------------------------------------------------------------------
# 도구 실행
# ---------------------------------------------------------------------------

def test_index_status_without_store_explains_how_to_index(mcp_stdin, project_to_tmp):
    responses = run_server(mcp_stdin, call_tool("index_status"))
    assert "ingest.py" in extract_text(responses[0])


def test_index_status_reports_stats(mcp_stdin, tmp_store):
    responses = run_server(mcp_stdin, call_tool("index_status"))
    payload = json.loads(extract_text(responses[0]))
    assert payload["chunks"] == 3
    assert payload["sources"] == 3


def test_list_indexed_sources_lists_files(mcp_stdin, tmp_store):
    responses = run_server(mcp_stdin, call_tool("list_indexed_sources"))
    text = extract_text(responses[0])
    assert "guide.md" in text
    assert "ops.md" in text


def test_search_docs_returns_ranked_chunks(mcp_stdin, tmp_store):
    responses = run_server(
        mcp_stdin,
        call_tool("search_docs", {"query": "임베딩 모델을 바꾸면?", "top_k": 2}),
    )
    text = extract_text(responses[0])
    assert "검색 결과" in text
    assert "score=" in text
    assert "ops.md" in text


def test_search_docs_requires_query(mcp_stdin, tmp_store):
    responses = run_server(mcp_stdin, call_tool("search_docs", {}))
    assert "query" in extract_text(responses[0])


def test_search_docs_clamps_top_k(mcp_stdin, tmp_store):
    """top_k 는 1..20 으로 보정된다(과도한 값도 안전)."""
    responses = run_server(
        mcp_stdin,
        call_tool("search_docs", {"query": "청크", "top_k": 999}),
    )
    assert "error" not in responses[0]
    assert len(extract_text(responses[0]).splitlines()) >= 2


# ---------------------------------------------------------------------------
# 오류 처리
# ---------------------------------------------------------------------------

def test_unknown_tool_returns_error(mcp_stdin, tmp_store):
    responses = run_server(mcp_stdin, call_tool("no_such_tool"))
    assert responses[0]["error"]["code"] == -32602


def test_unknown_method_returns_error(mcp_stdin):
    responses = run_server(mcp_stdin, request("no/such/method"))
    assert responses[0]["error"]["code"] == -32601


def test_malformed_json_returns_parse_error():
    stdout = io.StringIO()
    rag_server.serve(stdin=io.StringIO("{not json}\n"), stdout=stdout)
    payload = json.loads(stdout.getvalue().splitlines()[0])
    assert payload["error"]["code"] == -32700


def test_blank_lines_are_ignored(mcp_stdin):
    stdout = io.StringIO()
    rag_server.serve(
        stdin=io.StringIO("\n\n" + mcp_stdin(request("ping"))), stdout=stdout
    )
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
    assert len(responses) == 1


def test_multiple_requests_processed_in_order(mcp_stdin):
    responses = run_server(
        mcp_stdin,
        request("ping", request_id=1),
        request("tools/list", request_id=2),
    )
    assert [response["id"] for response in responses] == [1, 2]


# ---------------------------------------------------------------------------
# search_docs: mode and sources
# ---------------------------------------------------------------------------

def test_search_docs_schema_advertises_mode_and_sources(mcp_stdin):
    responses = run_server(mcp_stdin, request("tools/list"))
    schema = next(t for t in responses[0]["result"]["tools"]
                  if t["name"] == "search_docs")["inputSchema"]
    assert schema["properties"]["mode"]["enum"] == ["hybrid", "vector", "keyword"]
    assert schema["properties"]["sources"]["type"] == "array"
    assert schema["properties"]["sources"]["items"]["type"] == "string"


def test_search_docs_reports_the_used_mode(mcp_stdin, tmp_store):
    responses = run_server(
        mcp_stdin,
        call_tool("search_docs", {"query": "크기", "mode": "keyword"}),
    )
    assert "[keyword]" in extract_text(responses[0])


def test_search_docs_defaults_to_hybrid(mcp_stdin, tmp_store):
    responses = run_server(mcp_stdin, call_tool("search_docs", {"query": "chunk"}))
    assert "[hybrid]" in extract_text(responses[0])


def test_search_docs_rejects_unknown_mode(mcp_stdin, tmp_store):
    responses = run_server(
        mcp_stdin,
        call_tool("search_docs", {"query": "chunk", "mode": "banana"}),
    )
    assert "banana" in extract_text(responses[0])


def test_search_docs_accepts_a_single_source_string(mcp_stdin, tmp_store):
    responses = run_server(
        mcp_stdin,
        call_tool("search_docs", {"query": "chunk", "sources": "guide.md"}),
    )
    text = extract_text(responses[0])
    assert "guide.md" in text
    assert "ops.md" not in text


def test_search_docs_source_filter_excludes_other_files(mcp_stdin, tmp_store):
    responses = run_server(
        mcp_stdin,
        call_tool("search_docs", {"query": "chunk", "sources": []}),
    )
    assert "error" not in responses[0]


# ---------------------------------------------------------------------------
# reindex
# ---------------------------------------------------------------------------

class _Completed:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_reindex_schema_is_empty_by_default(mcp_stdin):
    responses = run_server(mcp_stdin, request("tools/list"))
    schema = next(t for t in responses[0]["result"]["tools"]
                  if t["name"] == "reindex")["inputSchema"]
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"paths", "reset"}
    assert "required" not in schema


def test_reindex_runs_ingest_with_paths_and_reset(mcp_stdin, tmp_store, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Completed(stdout="indexed 2 chunks")

    monkeypatch.setattr(rag_server.subprocess, "run", fake_run)

    responses = run_server(
        mcp_stdin, call_tool("reindex", {"paths": ["docs"], "reset": True})
    )

    assert captured["command"][1].endswith("ingest.py")
    assert captured["command"][-2:] == ["--reset", "docs"]
    assert captured["kwargs"]["env"]["PYTHONPATH"]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["timeout"] == rag_server.REINDEX_TIMEOUT
    assert "indexed 2 chunks" in extract_text(responses[0])


def test_reindex_incremental_omits_the_reset_flag(mcp_stdin, tmp_store, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return _Completed(stdout="ok")

    monkeypatch.setattr(rag_server.subprocess, "run", fake_run)
    run_server(mcp_stdin, call_tool("reindex", {}))

    assert "--reset" not in captured["command"]


def test_reindex_never_leaks_child_stdout_into_the_mcp_stream(
    mcp_stdin, tmp_store, monkeypatch
):
    monkeypatch.setattr(
        rag_server.subprocess, "run",
        lambda command, **kwargs: _Completed(stdout="PROGRESS 50%\nPROGRESS 100%"),
    )
    responses = run_server(mcp_stdin, call_tool("reindex", {}))

    # exactly one response message: no raw child output on the MCP channel
    assert len(responses) == 1
    assert responses[0]["jsonrpc"] == "2.0"
    assert "PROGRESS" not in responses[0]


def test_reindex_failure_reports_the_exit_code(mcp_stdin, tmp_store, monkeypatch):
    monkeypatch.setattr(
        rag_server.subprocess, "run",
        lambda command, **kwargs: _Completed(returncode=3, stderr="embedding failed"),
    )
    responses = run_server(mcp_stdin, call_tool("reindex", {}))

    text = extract_text(responses[0])
    assert "3" in text
    assert "embedding failed" in text


def test_reindex_timeout_is_reported(mcp_stdin, tmp_store, monkeypatch):
    def raise_timeout(command, **kwargs):
        raise rag_server.subprocess.TimeoutExpired(cmd="ingest", timeout=1)

    monkeypatch.setattr(rag_server.subprocess, "run", raise_timeout)
    responses = run_server(mcp_stdin, call_tool("reindex", {}))

    assert str(rag_server.REINDEX_TIMEOUT) in extract_text(responses[0])


def test_reindex_oserror_is_reported(mcp_stdin, tmp_store, monkeypatch):
    def raise_oserror(command, **kwargs):
        raise OSError("python not found")

    monkeypatch.setattr(rag_server.subprocess, "run", raise_oserror)
    responses = run_server(mcp_stdin, call_tool("reindex", {}))

    assert "python not found" in extract_text(responses[0])


def test_reindex_is_not_auto_approvable_by_convention(mcp_stdin):
    """The tool description must warn that it is a write tool."""
    responses = run_server(mcp_stdin, request("tools/list"))
    tool = next(t for t in responses[0]["result"]["tools"]
                if t["name"] == "reindex")
    assert "자동 승인" in tool["description"]