"""test_embeddings_llama_cpp.py -- llama.cpp 임베딩 provider 테스트.

외부 서비스(GGUF 모델, llama-server, Ollama) 없이 돌도록, 실패 경로와
객체 생성(네트워크 호출 없음)만 검증한다. 실제 임베딩 계산은 llama-cpp-python
또는 llama-server 가 필요한 영역이라 여기서 다루지 않는다.
"""

from __future__ import annotations

import pytest

import embeddings_llama_cpp as llm
import rag_core as core


def test_supports_recognises_llama_providers():
    assert llm.supports("llama_cpp") is True
    assert llm.supports("llama_cpp_server") is True
    assert llm.supports("LLAMA_CPP") is True  # 대소문자 무시
    assert llm.supports("ollama") is False
    assert llm.supports("openai") is False


def test_build_llama_cpp_missing_model_path_raises_runtime_error():
    cfg = {"embedding": {"provider": "llama_cpp", "llama_cpp": {"modelPath": ""}}}
    with pytest.raises(RuntimeError):
        llm.build_llama_cpp_embeddings(cfg)


def test_build_llama_cpp_unknown_provider_raises_value_error():
    cfg = {"embedding": {"provider": "ollama"}}
    with pytest.raises(ValueError):
        llm.build_llama_cpp_embeddings(cfg)


def test_build_llama_cpp_server_returns_openai_embeddings():
    # 생성은 네트워크 호출을 하지 않으므로 서버 없이도 안전하다.
    cfg = {"embedding": {"provider": "llama_cpp_server"}}
    emb = llm.build_llama_cpp_embeddings(cfg)
    assert type(emb).__name__ == "OpenAIEmbeddings"


def test_load_config_defaults_include_llama_cpp_sections(tmp_path):
    cfg = core.load_config(tmp_path / "no_such_config.json")
    assert cfg["embedding"]["provider"] == "ollama"
    assert cfg["embedding"]["llama_cpp"]["modelPath"] == ""
    assert cfg["embedding"]["llama_cpp"]["nCtx"] == 2048
    assert cfg["embedding"]["llama_cpp_server"]["apiBase"].endswith("8080/v1")


def test_build_embeddings_delegates_to_llama_cpp_provider():
    # rag_core.build_embeddings 가 llama.cpp 계열 provider 를 위임하는지 확인.
    emb = core.build_embeddings({"embedding": {"provider": "llama_cpp_server"}})
    assert type(emb).__name__ == "OpenAIEmbeddings"

    bad = {"embedding": {"provider": "llama_cpp", "llama_cpp": {"modelPath": ""}}}
    with pytest.raises(RuntimeError):
        core.build_embeddings(bad)
