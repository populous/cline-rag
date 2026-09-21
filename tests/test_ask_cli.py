"""test_ask_cli.py -- src/ask.py CLI 테스트 (외부 서비스 불필요).

목적: 파이프/리다이렉션 없이 커맨드라인 인자로 바로 질문할 수 있는 CLI
(`python src/ask.py "질문"`)가 rag_core.search_documents() 와 동일한 결과를
사람이 읽는 형식/JSON 형식으로 정확히 출력하는지 검증한다.
"""

from __future__ import annotations

import json

import pytest

import ask
import rag_core as core


@pytest.fixture
def cli_store(seeded_store, monkeypatch):
    """ask.py 가 seeded_store 의 저장소를 그대로 쓰도록 cfg 를 고정한다."""
    _store, cfg = seeded_store
    monkeypatch.setattr(core, "load_config", lambda path=None: cfg)
    return cfg


def test_ask_prints_human_readable_results(cli_store, capsys):
    exit_code = ask.main(["임베딩 모델을 바꾸면 전체 재색인이 필요하다.", "--top-k", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[hybrid] 검색 결과" in captured.out
    assert "score=" in captured.out
    assert "alpha.md#chunk1" in captured.out


def test_ask_keyword_mode(cli_store, capsys):
    exit_code = ask.main(["재색인", "--mode", "keyword"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[keyword]" in captured.out
    assert "재색인" in captured.out


def test_ask_json_output_is_parseable(cli_store, capsys):
    exit_code = ask.main(["청크", "--top-k", "2", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["query"] == "청크"
    assert payload["mode"] == "hybrid"
    assert isinstance(payload["hits"], list)
    assert len(payload["hits"]) <= 2


def test_ask_sources_filter(cli_store, capsys, tmp_path):
    only_beta = [str(tmp_path / "beta.md")]
    exit_code = ask.main(["Ollama", "--sources", *only_beta])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "beta.md" in captured.out
    assert "alpha.md" not in captured.out


def test_ask_no_match_reports_empty_result(cli_store, capsys):
    exit_code = ask.main(["zzzznomatch", "--mode", "keyword"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "검색 결과가 없습니다" in captured.out


def test_ask_missing_store_reports_error(tmp_path, monkeypatch, capsys, fake_embed):
    cfg = core.load_config()
    cfg["store"]["path"] = str(tmp_path / "absent_store")
    monkeypatch.setattr(core, "load_config", lambda path=None: cfg)

    exit_code = ask.main(["무엇이든"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "오류" in captured.err


def test_ask_help_does_not_crash(capsys):
    with pytest.raises(SystemExit) as exc_info:
        ask.main(["-h"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "query" in captured.out
