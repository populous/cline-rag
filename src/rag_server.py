"""rag_server.py -- Cline/OpenCode 등 MCP 클라이언트에 붙이는 RAG MCP 서버.

MCP 의 stdio 전송(줄 단위 JSON-RPC 2.0)은 표준 라이브러리로 직접 구현한다.
검색/색인 로직은 rag_core.py 를 통해 LangChain + LangGraph + Chroma 를 쓴다
(자세한 내용은 requirements.txt, README.md 참고).

제공 도구(tools):
  * search_docs(query, top_k, min_score, sources, mode) : 문서 검색
  * list_indexed_sources()                              : 색인된 파일 목록
  * index_status()                                      : 색인 현황
  * reindex(paths, reset)                                : 재색인(쓰기 도구)

주의: stdout 은 MCP 프로토콜 전용이다. 로그는 반드시 stderr 로 보낸다.
"""

from __future__ import annotations

import json
import os
import subprocess
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
SERVER_VERSION = "2.4.0"
DEFAULT_PROTOCOL = "2025-06-18"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_docs",
        "description": (
            "로컬 문서 저장소에서 질문과 의미상 가장 가까운 내용을 검색한다. "
            "코드/문서에 대한 질문에 답하기 전에 먼저 호출한다."
            "mode: hybrid (default, vector+keyword via RRF) | vector (cosine) | keyword (BM25); "
            "sources restricts the search to specific indexed files."
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
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "이 경로들만 검색한다(색인된 파일 경로). 생략하면 전체.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["hybrid", "vector", "keyword"],
                    "description": "hybrid=의미+키워드 RRF(기본), vector=코사인, keyword=BM25",
                    "default": "hybrid",
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
    {
        "name": "reindex",
        "description": (
            "문서를 다시 색인한다(쓰기 도구). 문서를 추가·수정한 뒤 호출한다. "
            "색인은 별도 프로세스로 실행되므로 서버 stdout(MCP 통신)은 오염되지 않는다. "
            "읽기 전용이 아니므로 자동 승인 목록(autoApprove/permission allow)에 넣지 말 것."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "색인할 파일/폴더. 생략하면 기본값(docs/)만 다시 색인한다.",
                },
                "reset": {
                    "type": "boolean",
                    "description": "true 면 저장소를 비우고 전체 재색인한다(임베딩 모델 변경 시).",
                    "default": False,
                },
            },
        },
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


#: Ranking used when the client does not ask for a specific mode.
DEFAULT_SEARCH_MODE = "hybrid"

#: Upper bound for a reindex run (embedding a cold model can be slow).
REINDEX_TIMEOUT = 900


def normalise_sources(raw: Any) -> list[str] | None:
    """Accept a list of source paths (or a single string) from the client."""
    if not raw:
        return None
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple)):
        candidates = [str(item) for item in raw]
    else:
        return None
    selected = [item for item in candidates if item.strip()]
    return selected or None


def tool_search_docs(args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        return text_content("오류: query 인자가 필요합니다.")

    top_k = int(args.get("top_k", 5) or 5)
    top_k = max(1, min(top_k, 20))
    min_score = float(args.get("min_score", 0.0) or 0.0)
    mode = str(args.get("mode") or DEFAULT_SEARCH_MODE).lower()
    sources = normalise_sources(args.get("sources"))

    cfg, db_path = load_config_and_store()
    try:
        hits = core.search_documents(query, top_k=top_k, min_score=min_score,
                                     sources=sources, mode=mode,
                                     cfg=cfg, db_path=db_path)
    except ValueError as exc:
        return text_content(f"오류: {exc}")
    except FileNotFoundError as exc:
        return text_content(f"오류: {exc}")
    except Exception as exc:  # noqa: BLE001 - 도구는 예외를 텍스트로 반환
        log(traceback.format_exc())
        return text_content(f"검색 실패: {exc}")

    if not hits:
        return text_content(f"'{query}' 에 대한 검색 결과가 없습니다.")

    lines = [f"'{query}' [{mode}] 검색 결과 {len(hits)}건", ""]
    for rank, hit in enumerate(hits, start=1):
        lines.append(
            f"[{rank}] score={hit['score']:.4f} | "
            f"{hit['source']}#chunk{hit['chunk_index']}"
        )
        lines.append(hit["text"])
        lines.append("")
    return text_content("\n".join(lines).rstrip())


def store_exists(db_path: Path) -> bool:
    """Chroma persist_directory 가 실제로 색인된 상태인지 확인한다."""
    return db_path.is_dir() and any(db_path.iterdir())


def tool_list_indexed_sources(_args: dict) -> dict:
    cfg, db_path = load_config_and_store()
    if not store_exists(db_path):
        return text_content("색인 저장소가 아직 없습니다. ingest.py 를 먼저 실행하세요.")
    store = core.connect(db_path, cfg)
    items = core.list_sources(store)
    if not items:
        return text_content("색인된 파일이 없습니다.")
    lines = [f"색인된 파일 {len(items)}개", ""]
    lines.extend(f"{item['chunks']:5d}  {item['source']}" for item in items)
    return text_content("\n".join(lines))


def tool_index_status(_args: dict) -> dict:
    cfg, db_path = load_config_and_store()
    if not store_exists(db_path):
        return text_content("색인 저장소가 아직 없습니다. ingest.py 를 먼저 실행하세요.")
    store = core.connect(db_path, cfg)
    stats = core.store_stats(store)
    payload = {"store": str(db_path), **stats}
    return text_content(json.dumps(payload, ensure_ascii=False, indent=2))


def tool_reindex(args: dict) -> dict:
    """Re-run ingestion in a child process.

    Running ingest.py in-process would print progress to stdout, which is the
    MCP transport channel, and would corrupt the protocol stream. Spawning a
    separate interpreter keeps stdout clean.
    """
    paths = [str(path) for path in (args.get("paths") or [])]
    reset = bool(args.get("reset", False))

    command = [sys.executable, str(SRC_DIR / "ingest.py")]
    if reset:
        command.append("--reset")
    command.extend(paths)

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(SRC_DIR)

    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_DIR),
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=REINDEX_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return text_content(f"색인 시간 초과: {REINDEX_TIMEOUT}초")
    except OSError as exc:
        log(traceback.format_exc())
        return text_content(f"색인 실행 실패: {exc}")

    output = (completed.stdout or "").strip()
    if completed.returncode != 0:
        log(f"reindex exited with code {completed.returncode}")
        detail = (completed.stderr or output or "출력 없음").strip()
        return text_content(f"색인 실패(exit={completed.returncode}):\n{detail[-1500:]}")

    _config, db_path = load_config_and_store()
    tail = "\n".join(output.splitlines()[-25:])
    return text_content(f"색인 완료: {db_path}\n\n{tail}")


TOOL_HANDLERS = {
    "search_docs": tool_search_docs,
    "list_indexed_sources": tool_list_indexed_sources,
    "index_status": tool_index_status,
    "reindex": tool_reindex,
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

