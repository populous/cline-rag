"""ask.py -- 터미널에서 바로 질문하고 검색 결과를 보는 CLI.

MCP/JSON-RPC 를 몰라도, 파이프/리다이렉션 인코딩 문제 없이 곧바로 검색을
확인할 수 있게 만든 도구다. 질문은 커맨드라인 인자로 받는다(파이프로 흘려
보내지 않으므로 Windows 콘솔 코드페이지에 영향을 받지 않는다).

사용 예(프로젝트 루트에서 실행):
    python src\\ask.py "연차는 반차 단위로도 신청할 수 있니?"
    python src\\ask.py --top-k 3 --mode vector "청크 크기는 얼마가 적당한가?"
    python src\\ask.py --json "청크 크기" > result.json   # 스크립트 연동용

내부적으로 rag_server.py 의 tool_search_docs() 와 동일한 코드 경로
(rag_core.search_documents)를 그대로 호출하므로, 여기서 본 결과는 Cline 이
search_docs 도구를 호출했을 때와 100% 동일하다.

MCP(Cline 연동) 설정 관련 옵션(질문 없이 사용 가능):
    python src\\ask.py --mcp-print                # 등록용 JSON 조각만 출력
    python src\\ask.py --mcp-status                # 실제 등록 여부/경로 확인
    python src\\ask.py --mcp-install                # 설정 파일에 자동 등록
    python src\\ask.py --mcp-install --force        # 기존 등록을 덮어쓰기
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _venv_python_hint() -> str:
    """프로젝트 루트 기준 .venv 파이썬의 예상 경로를 안내 문구로 만든다."""
    project_dir = Path(__file__).resolve().parent.parent
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
    return str(venv_python)


try:
    import rag_core as core
except ModuleNotFoundError as exc:
    if exc.name in {"langchain_community", "langchain_core", "langchain_chroma",
                    "langchain_text_splitters", "langgraph"}:
        for _stream in (sys.stdout, sys.stderr):
            _reconfigure = getattr(_stream, "reconfigure", None)
            if callable(_reconfigure):
                try:
                    _reconfigure(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass
        hint = _venv_python_hint()
        print(
            "오류: 필요한 패키지({name})를 찾을 수 없습니다.\n"
            "지금 실행한 python 이 이 프로젝트의 가상환경(.venv)이 아닌 것 같습니다.\n"
            "실행한 인터프리터: {executable}\n\n"
            "아래처럼 .venv 의 python 으로 실행하세요:\n"
            "  {hint} src\\ask.py \"질문\"\n\n"
            ".venv 가 아직 없다면 먼저 setup.ps1 을 실행하세요:\n"
            "  powershell -ExecutionPolicy Bypass -File .\\setup.ps1".format(
                name=exc.name, executable=sys.executable, hint=hint,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    raise


def force_utf8_output() -> None:
    """Windows 콘솔의 cp949/cp1252 코드페이지와 무관하게 UTF-8로 출력한다."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


# --------------------------------------------------------------------------
# MCP(Cline 연동) 설정 관련 유틸리티
# --------------------------------------------------------------------------

MCP_SERVER_NAME = "cline-rag"

DEFAULT_MCP_SETTINGS_PATH = (
    Path.home() / ".cline" / "data" / "settings" / "cline_mcp_settings.json"
)


def _project_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _venv_python_path() -> Path:
    return _project_dir() / ".venv" / "Scripts" / "python.exe"


def _rag_server_path() -> Path:
    return _project_dir() / "src" / "rag_server.py"


def build_mcp_entry() -> dict:
    """Cline 의 mcpServers 항목에 넣을 이 프로젝트의 설정 조각을 만든다."""
    return {
        "command": str(_venv_python_path()),
        "args": [str(_rag_server_path())],
        "env": {},
        "disabled": False,
        "autoApprove": ["search_docs", "list_indexed_sources", "index_status"],
    }


def format_mcp_snippet() -> str:
    payload = {"mcpServers": {MCP_SERVER_NAME: build_mcp_entry()}}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def check_mcp_status(settings_path: Path) -> tuple[int, str]:
    """등록 여부/경로 일치 여부를 확인하고 (exit_code, 메시지) 를 돌려준다."""
    venv_python = _venv_python_path()
    if not settings_path.exists():
        return 1, (
            f"Cline MCP 설정 파일이 없습니다: {settings_path}\n"
            "아직 Cline 을 실행하지 않았거나 경로가 다를 수 있습니다.\n"
            "--mcp-install 로 새로 만들 수 있습니다."
        )
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return 1, f"설정 파일을 읽을 수 없습니다: {settings_path}\n({exc})"

    servers = data.get("mcpServers", {})
    entry = servers.get(MCP_SERVER_NAME)
    if entry is None:
        return 1, (
            f"'{MCP_SERVER_NAME}' 서버가 아직 등록되어 있지 않습니다: {settings_path}\n"
            "--mcp-install 로 등록할 수 있습니다."
        )

    lines = [f"'{MCP_SERVER_NAME}' 등록됨: {settings_path}", f"  command : {entry.get('command')}",
              f"  args    : {entry.get('args')}", f"  disabled: {entry.get('disabled', False)}"]

    problems = []
    if entry.get("command") != str(venv_python):
        problems.append(
            f"  경고: command 가 이 프로젝트의 .venv 경로와 다릅니다.\n"
            f"        기대값: {venv_python}"
        )
    if not venv_python.exists():
        problems.append(f"  경고: {venv_python} 가 실제로 존재하지 않습니다 (setup.ps1 을 먼저 실행하세요)")
    if entry.get("disabled"):
        problems.append("  경고: disabled=true 라서 Cline 이 이 서버를 쓰지 않습니다")

    if problems:
        lines.append("")
        lines.extend(problems)
        return 1, "\n".join(lines)
    return 0, "\n".join(lines)


def install_mcp_entry(settings_path: Path, force: bool) -> tuple[int, str]:
    """설정 파일에 이 프로젝트의 MCP 서버 항목을 병합해서 써준다."""
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return 1, f"기존 설정 파일을 읽을 수 없습니다: {settings_path}\n({exc})"
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    if MCP_SERVER_NAME in servers and not force:
        return 1, (
            f"'{MCP_SERVER_NAME}' 은 이미 등록되어 있습니다: {settings_path}\n"
            "덮어쓰려면 --force 를 함께 쓰세요."
        )

    servers[MCP_SERVER_NAME] = build_mcp_entry()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0, f"'{MCP_SERVER_NAME}' 을 등록했습니다: {settings_path}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="색인된 문서에 바로 질문하고 검색 결과를 확인합니다."
    )
    parser.add_argument("query", nargs="?", default=None,
                        help="검색할 질문이나 키워드 (--mcp-* 옵션만 쓸 때는 생략 가능)")
    parser.add_argument("--top-k", type=int, default=3, help="가져올 청크 수 (기본 3)")
    parser.add_argument("--min-score", type=float, default=0.0,
                        help="코사인 유사도 하한 (vector 모드에서만 적용, 기본 0.0)")
    parser.add_argument("--mode", choices=list(core.MODES), default="hybrid",
                        help="hybrid(기본)|vector|keyword")
    parser.add_argument("--sources", nargs="*", default=None,
                        help="이 파일 경로들만 검색한다(생략하면 전체)")
    parser.add_argument("--config", default=None, help="config.json 경로")
    parser.add_argument("--json", action="store_true",
                        help="사람이 읽는 형식 대신 JSON 으로 출력한다")

    mcp_group = parser.add_argument_group("MCP (Cline 연동) 설정")
    mcp_group.add_argument("--mcp-print", action="store_true",
                        help="Cline mcp_settings.json 에 넣을 JSON 조각을 출력하고 종료")
    mcp_group.add_argument("--mcp-status", action="store_true",
                        help="이 프로젝트가 Cline 에 등록되어 있는지 확인하고 종료")
    mcp_group.add_argument("--mcp-install", action="store_true",
                        help="Cline 설정 파일에 이 프로젝트를 자동으로 등록하고 종료")
    mcp_group.add_argument("--force", action="store_true",
                        help="--mcp-install 시 기존 등록을 덮어쓴다")
    mcp_group.add_argument("--mcp-settings", default=str(DEFAULT_MCP_SETTINGS_PATH),
                        help=f"Cline MCP 설정 파일 경로 (기본: {DEFAULT_MCP_SETTINGS_PATH})")

    args = parser.parse_args(argv)
    wants_mcp_action = args.mcp_print or args.mcp_status or args.mcp_install
    if not wants_mcp_action and args.query is None:
        parser.error("query 인자가 필요합니다 (또는 --mcp-print/--mcp-status/--mcp-install 중 하나를 쓰세요)")
    return args


def format_human(query: str, mode: str, hits: list[dict]) -> str:
    if not hits:
        return f"'{query}' 에 대한 검색 결과가 없습니다. (mode={mode})"
    lines = [f"'{query}' [{mode}] 검색 결과 {len(hits)}건", ""]
    for rank, hit in enumerate(hits, start=1):
        lines.append(f"[{rank}] score={hit['score']} | {hit['source']}#chunk{hit['chunk_index']}")
        lines.append(hit["text"])
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    force_utf8_output()
    args = parse_args(argv)

    if args.mcp_print:
        print(format_mcp_snippet())
        return 0
    if args.mcp_status:
        code, message = check_mcp_status(Path(args.mcp_settings))
        print(message)
        return code
    if args.mcp_install:
        code, message = install_mcp_entry(Path(args.mcp_settings), force=args.force)
        print(message)
        return code

    cfg = core.load_config(args.config)

    try:
        hits = core.search_documents(
            args.query, top_k=args.top_k, min_score=args.min_score,
            sources=args.sources, mode=args.mode, cfg=cfg,
        )
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"query": args.query, "mode": args.mode, "hits": hits},
                         ensure_ascii=False, indent=2))
    else:
        print(format_human(args.query, args.mode, hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
