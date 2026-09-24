"""check_ollama_gpu.py -- Ollama 임베딩이 GPU/CPU 어디서 도는지 진단.

목적
----
GTX 1060 + 구형 드라이버에서 Ollama 의 CUDA 러너가

    CUDA error: the provided PTX was compiled with an unsupported toolchain

으로 죽는 문제를 재현·판별하기 위한 **읽기 전용** 진단 스크립트다.

- 메인 앱과 동일한 코드 경로(``rag_core.build_embeddings``)로 실제 임베딩을
  호출해 PASS/FAIL 을 판정한다.
- ``--require-gpu`` 를 주면 "GPU 러너 사용"까지 통과 조건으로 본다
  (드라이버 업데이트 후 GPU 동작 확인용).
- 색인/저장소는 전혀 건드리지 않는다.

실행:
    python examples\\06_ollama_gpu\\check_ollama_gpu.py
    python examples\\06_ollama_gpu\\check_ollama_gpu.py --require-gpu
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import rag_core as core  # noqa: E402


SAMPLE_TEXTS = [
    "연차는 반차(0.5일) 단위로도 신청할 수 있다.",
    "미사용 연차는 다음 해로 최대 5일까지 이월할 수 있다.",
]

# 실패 원인을 사람이 이해하기 쉽게 매핑하기 위한 시그니처 문자열.
CUDA_PTX_SIGNATURES = (
    "unsupported toolchain",
    "llama-server process has terminated",
    "0xc0000409",
)


def force_utf8_output() -> None:
    """Windows 콘솔 코드페이지와 무관하게 UTF-8 로 출력한다."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def detect_gpu() -> str | None:
    """nvidia-smi 로 GPU 이름/드라이버 버전을 읽는다. 없으면 None."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return None
    try:
        proc = subprocess.run(
            [nvidia_smi, "--query-gpu=name,driver_version,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def http_get_json(url: str, timeout: int = 10) -> dict:
    """표준 라이브러리만으로 Ollama HTTP API 를 호출해 JSON 을 돌려준다."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def runner_via_ps(base_url: str) -> str:
    """/api/ps 의 size_vram 으로 현재 러너(GPU/CPU)를 추정한다.

    Ollama 는 모델을 CPU 로 띄우면 size_vram=0, GPU 에 올리면 VRAM 사용량을
    채워준다. 서버가 없거나 정보가 없으면 "unknown".
    """
    try:
        payload = http_get_json(base_url.rstrip("/") + "/api/ps")
    except (urllib.error.URLError, OSError, ValueError):
        return "unknown"
    models = payload.get("models") or []
    if not models:
        return "unknown"
    vram = sum(int(m.get("size_vram", 0) or 0) for m in models)
    return "gpu" if vram > 0 else "cpu"


def is_ptx_error(message: str) -> bool:
    lowered = message.lower()
    return any(sig in lowered for sig in CUDA_PTX_SIGNATURES)


def main(argv: list[str] | None = None) -> int:
    force_utf8_output()
    parser = argparse.ArgumentParser(description="Ollama 임베딩 GPU/CPU 진단")
    parser.add_argument("--require-gpu", action="store_true",
                        help="GPU 러너 사용까지 통과 조건으로 본다")
    args = parser.parse_args(argv)

    cfg = core.load_config()
    provider = str(cfg["embedding"]["provider"]).lower()
    conf = cfg["embedding"].get(provider, {}) or {}
    base_url = conf.get("apiBase", "http://127.0.0.1:11434")

    print("== cline-rag Ollama 임베딩 진단 ==")
    print(f"  provider : {provider}")
    print(f"  model    : {conf.get('model')}")
    print(f"  apiBase  : {base_url}")

    # 1) GPU 존재 여부
    gpu_info = detect_gpu()
    if gpu_info:
        print(f"  GPU      : {gpu_info}")
    else:
        print("  GPU      : 감지 안 됨(nvidia-smi 없음/실패)")

    # 2) Ollama 서버 상태
    try:
        tags = http_get_json(base_url.rstrip("/") + "/api/tags")
        names = [m.get("name") for m in tags.get("models", [])]
        print(f"  서버     : 연결됨, 모델 {len(names)}개")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  서버     : 연결 실패 ({exc})")
        print(f"\n사전 준비: Ollama 서버를 켜세요 →  {base_url}")
        return 2

    # 3) 임베딩 실측 (메인 앱과 동일 경로)
    try:
        embeddings = core.build_embeddings(cfg)
        vectors = embeddings.embed_documents(SAMPLE_TEXTS)
    except Exception as exc:  # noqa: BLE001
        message = f"{exc}"
        print(f"\n[FAIL] 임베딩 실패: {message}")
        if is_ptx_error(message):
            print("원인: CUDA/PTX 호환 오류(드라이버가 Ollama CUDA 러너보다 오래됨).")
            print("해결: NVIDIA 드라이버 업데이트 후 재시도, 또는 CPU 강제(OLLAMA_LLM_LIBRARY=cpu).")
        return 1

    dims = sorted({len(v) for v in vectors})
    print(f"\n[PASS] 임베딩 성공: {len(vectors)}개 벡터, 차원 {dims}")

    # 4) 러너 판별
    runner = runner_via_ps(base_url)
    print(f"  러너     : {runner}")

    # 5) --require-gpu 검증
    if args.require_gpu:
        if runner == "gpu":
            print("\n[PASS] GPU 러너 사용 확인.")
            return 0
        if runner == "cpu":
            print("\n[FAIL] GPU 미사용(CPU 러너). OLLAMA_LLM_LIBRARY=cpu 해제 + Ollama 재시작 후 재시도.")
            return 1
        print("\n[FAIL] GPU 사용 여부를 판별할 수 없습니다(모델 로드/서버 상태 확인).")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
