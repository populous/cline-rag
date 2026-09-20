"""rag_server.py -- Cline 에 붙이는 RAG MCP 서버 (표준 라이브러리만 사용).

MCP 의 stdio 전송(줄 단위 JSON-RPC 2.0)을 직접 구현하므로
`pip install` 없이 바로 동작한다.

제공 도구(tools):
  * search_docs(query, top_k, min_score) : 의미 기반 문서 검색
  * list_indexed_sources()               : 색인된 파일 목록
  * index_status()                       : 색인 현황(청크/파일/차원)

주의: stdout 은 MCP 프로토콜 전용이다. 로그는 반드시 stderr 로 보낸다.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

# 소스는 src/ 에 있고 설정/저장소는 프로젝트 루트에 있다.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import rag_core as core  # noqa: E402  (경로 설정 후 임포트)

# 프로젝트 트: 설정 파일과 저장소를 찾는 기준. 테스트에서 monkeypatch 한다.
PROJECT_DIR = core.PROJECT_DIR

SERVER_NAME = "cline-rag"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_docs",
        "description": (
            "로컬 문서 저장소에서 질문과 의미상 가장 가까운 내용을 검색한다. "
            "코드/문서에 대한 질문에 답하기 전에 먼저 호출한다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 질문이나 키워드",
                },
                "top_k": {
                    "type": "integer",
                    "description": "가져올 청크 수 (기본 5, 최대 20)",
                    "default": 5,
                },
                "min_score": {
                    "type": "number",
                    "description": "코사인 유사도 하한 (0.0~1.0, 기본 0.0)",
                    "default": 0.0,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_indexed_sources",
        "description": "색인된 파일 목록과 파일별 청크 수를 돌려준다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "index_status",
        "description": "색인 현황(총 청크 수, 총 파일 수, 벡터 차원)을 돌려준다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def log(message: str) -> None:
    """진단 로그는 stderr 로만 출력한다(stdout 은 MCP 전용)."""
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


def make_result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def text_content(text: str) -> dict:
    """도구 실행 결과를 MCP content 배열 형태로 감싼다."""
    return {"content": [{"type": "text", "text": text}]}


# --------------------------------------------------------------------------
# 도구 구현
# --------------------------------------------------------------------------

def load_config_and_store() -> tuple[dict, Path]:
    """설정과 저장소 경로를 **한 곳에서** 해석한다.

    세 도구가 모두 이 헬퍼를 쓰므로 경로 기준이 어긋날 수 없다.
    기준 디렉터리는 rag_server.py 가 있는 폴더(PROJECT_DIR)다.
    """
    cfg = core.load_config()
    return cfg, core.resolve_store_path(cfg, PROJECT_DIR)


def tool_search_docs(args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        return text_content("오류: query 인자가 필요합니다.")

    top_k = int(args.get("top_k", 5) or 5)
    top_k = max(1, min(top_k, 20))
    min_score = float(args.get("min_score", 0.0) or 0.0)

    cfg, db_path = load_config_and_store()
    try:
        hits = core.semantic_search(query, top_k=top_k, min_score=min_score,
                                    cfg=cfg, db_path=db_path)
    except FileNotFoundError as exc:
        return text_content(f"오류: {exc}")
    except Exception as exc:  # noqa: BLE001 - 도구는 예외를 텍스트로 반환
        log(traceback.format_exc())
        return text_content(f"검색 실패: {exc}")

    if not hits:
        return text_content(f"'{query}' 에 대한 검색 결과가 없습니다.")

    lines = [f"'{query}' 검색 결과 {len(hits)}건", ""]
    for rank, hit in enumerate(hits, start=1):
        lines.append(
            f"[{rank}] score={hit['score']:.4f} | "
            f"{hit['source']}#chunk{hit['chunk_index']}"
        )
        lines.append(hit["text"])
        lines.append("")
    return text_content("\n".join(lines).rstrip())


def tool_list_indexed_sources(_args: dict) -> dict:
    _cfg, db_path = load_config_and_store()
    if not db_path.is_file():
        return text_content("색인 저장소가 아직 없습니다. ingest.py 를 먼저 실행하세요.")
    conn = core.connect(db_path)
    try:
        items = core.list_sources(conn)
    finally:
        conn.close()
    if not items:
        return text_content("색인된 파일이 없습니다.")
    lines = [f"색인된 파일 {len(items)}개", ""]
    lines.extend(f"{item['chunks']:5d}  {item['source']}" for item in items)
    return text_content("\n".join(lines))


def tool_index_status(_args: dict) -> dict:
    _cfg, db_path = load_config_and_store()
    if not db_path.is_file():
        return text_content("색인 저장소가 아직 없습니다. ingest.py  먼저 실행하세요.")
    conn = core.connect(db_path)
    try:
        stats = core.store_stats(conn)
    finally:
        conn.close()
    payload = {"store": str(db_path), **stats}
    return text_content(json.dumps(payload, ensure_ascii=False, indent=2))


TOOL_HANDLERS = {
    "search_docs": tool_search_docs,
    "list_indexed_sources": tool_list_indexed_sources,
    "index_status": tool_index_status,
}


# --------------------------------------------------------------------------
# MCP 프로토콜 처리
# --------------------------------------------------------------------------

def handle_request(message: dict) -> dict | None:
    """JSON-RPC 요청 하나를 처리한다. 알림(notification)이면 None 을 돌려준다."""
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    # id 가 없는 메시지는 알림이므로 응답하지 않는다.
    if request_id is None:
        return None

    if method == "initialize":
        requested = params.get("protocolVersion")
        protocol = requested if requested in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        return make_result(request_id, {
            "protocolVersion": protocol,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "ping":
        return make_result(request_id, {})

    if method == "tools/list":
        return make_result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(str(name))
        if handler is None:
            return make_error(request_id, -32602, f"알 수 없는 도구: {name}")
        try:
            return make_result(request_id, handler(arguments))
        except Exception as exc:  # noqa: BLE001
            log(traceback.format_exc())
            return make_result(request_id, text_content(f"도구 실행 오류: {exc}"))

    return make_error(request_id, -32601, f"지원하지 않는 메서드: {method}")


def serve(stdin=None, stdout=None) -> int:
    """stdio 전송으로 MCP 메시지 루프를 돈다(줄 단위 JSON-RPC)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    # Windows 에서 줄바꿈이 \r\n 으로 변환되지 않도록 고정한다(MCP 호환).
    for stream in (stdin, stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(newline="\n", encoding="utf-8")
            except (ValueError, OSError):
                pass

    # stderr 로그도 UTF-8 로 고정한다(한국어 로그가 cp949 로 깨지는 것 방지).
    err_reconfigure = getattr(sys.stderr, "reconfigure", None)
    if callable(err_reconfigure):
        try:
            err_reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

    log(f"시작됨 (도구 {len(TOOLS)}개, 프로젝트 {PROJECT_DIR})")

    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = make_error(None, -32700, "JSON 파싱 오류")
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
            continue

        try:
            response = handle_request(message)
        except Exception as exc:  # noqa: BLE001
            log(traceback.format_exc())
            response = make_error(message.get("id"), -32603, f"내부 오류: {exc}")

        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()

    log("stdin 종료, 서버를 닫습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())

