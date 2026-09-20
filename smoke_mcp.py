"""test_mcp.py -- rag_server.py 가 MCP 규약대로 응답하는지 검사하는 클라이언트.

서버를 자식 프로세스로 띄우고 stdio 로 JSON-RPC 를 주고받는다.
외부 의존성 없이 표준 라이브러리만 사용한다.

사용:
    python test_mcp.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SERVER = PROJECT_DIR / "src" / "rag_server.py"


def send(proc: subprocess.Popen, payload: dict) -> dict | None:
    """요청을 한 줄로 보내고 응답 한 줄을 읽는다(알림이면 None)."""
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    if "id" not in payload:
        return None
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("서버가 응답하지 않고 종료되었습니다.")
    return json.loads(line)


def text_of(response: dict) -> str:
    """tools/call 응답에서 텍스트만 뽑아낸다."""
    try:
        return response["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(response, ensure_ascii=False)


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {label}" + (f" -- {detail}" if detail and not ok else ""))
        if not ok:
            failures.append(label)

    try:
        # 1) initialize
        init = send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18",
                       "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1.0"}},
        })
        check("initialize", bool(init and "result" in init),
              json.dumps(init, ensure_ascii=False)[:200] if init else "no response")
        server_info = (init or {}).get("result", {}).get("serverInfo", {})
        print(f"       서버: {server_info.get('name')} v{server_info.get('version')}")

        # 2) initialized 알림 (응답 없음이 정상)
        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 3) ping
        pong = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
        check("ping", bool(pong and "result" in pong))

        # 4) tools/list
        listing = send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        tools = (listing or {}).get("result", {}).get("tools", [])
        names = [t["name"] for t in tools]
        check("tools/list", len(tools) >= 3, str(names))
        print(f"       도구: {', '.join(names)}")
        for tool in tools:
            if "inputSchema" not in tool or "description" not in tool:
                check(f"tools/list 스키마({tool.get('name')})", False)

        # 5) index_status 호출
        status = send(proc, {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "index_status", "arguments": {}},
        })
        status_text = text_of(status or {})
        check("tools/call index_status", "error" not in (status or {}),
              status_text[:200])
        print("       " + status_text.replace("\n", " ")[:160])

        # 6) search_docs 호출
        search = send(proc, {
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "search_docs",
                       "arguments": {"query": "청크 크기는 얼마가 적당한가?", "top_k": 3}},
        })
        search_text = text_of(search or {})
        check("tools/call search_docs", "error" not in (search or {}),
              search_text[:200])
        first_line = search_text.splitlines()[0] if search_text else ""
        print("       " + first_line[:160])

        # 7) 알 수 없는 메서드는 에러여야 한다
        unknown = send(proc, {"jsonrpc": "2.0", "id": 6, "method": "no/such"})
        check("unknown method -> error", bool(unknown and "error" in unknown))

    finally:
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        stderr = proc.stderr.read() if proc.stderr else ""
        if stderr.strip():
            print("\n--- 서버 stderr ---")
            print(stderr.strip()[:1500])

    print()
    if failures:
        print(f"실패 {len(failures)}건: {', '.join(failures)}")
        return 1
    print("모든 검사 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
