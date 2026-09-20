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
    """rag_server.PROJECT_DIR  tmp 로 돌려 저장소를 리한다."""
    monkeypatch.setattr(rag_server, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(core, "embed_texts", lambda texts, cfg=None:
                        [fake_vector(text) for text in texts])
    return tmp_path


@pytest.fixture
def tmp_store(project_to_tmp):
    """tmp 프로젝트에 샘플 저장소를 만든다."""
    db_path = project_to_tmp / "rag_store.sqlite3"
    rows = [
        {"source": "guide.md", "chunk_index": 0,
         "text": "청크 크기는 800자, 겹침은 120자를 권장한다."},
        {"source": "ops.md", "chunk_index": 0,
         "text": "임베딩 모델을 바꾸면 전체 재색인이 필요하다."},
    ]
    conn = core.connect(db_path)
    conn.executemany(
        "INSERT INTO chunks(source, chunk_index, text, embedding, dim) VALUES(?,?,?,?,?)",
        [
            (row["source"], row["chunk_index"], row["text"],
             json.dumps(fake_vector(row["text"])), len(fake_vector(row["text"])))
            for row in rows
        ],
    )
    conn.commit()
    conn.close()
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

def test_tools_list_exposes_three_tools(mcp_stdin):
    responses = run_server(mcp_stdin, request("tools/list"))
    tools = {tool["name"]: tool for tool in responses[0]["result"]["tools"]}
    assert set(tools) == {"search_docs", "list_indexed_sources", "index_status"}


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
    assert payload["chunks"] == 2
    assert payload["sources"] == 2


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