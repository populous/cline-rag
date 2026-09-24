# 06. Ollama GPU(PTX/CUDA) 임베딩 검증 도구

Ollama 의 CUDA 러너가 구형 드라이버에서

```
CUDA error: the provided PTX was compiled with an unsupported toolchain
```

으로 죽는 문제를 재현·판별하는 **읽기 전용** 진단 스크립트다. 색인/저장소는
건드리지 않고, 메인 앱과 동일한 코드 경로(`rag_core.build_embeddings`)로
실제 임베딩을 호출해 PASS/FAIL 을 판정한다.

## 사전 준비

- Ollama 서버 실행(`ollama serve`), 모델 `nomic-embed-text` pull 완료
- NVIDIA GPU + 드라이버 (없으면 CPU 모드로만 동작)

## 실행

```powershell
cd C:\path\to\cline-rag
python examples\06_ollama_gpu\check_ollama_gpu.py
python examples\06_ollama_gpu\check_ollama_gpu.py --require-gpu
```

## 결과 해석

| exit code | 의미 |
|---|---|
| 0 | 임베딩 성공(차원 768). `--require-gpu` 시 GPU 러너 사용까지 확인 |
| 1 | 실패. 임베딩 실패(PTX/CUDA 오류 등) 또는 `--require-gpu` 시 GPU 미사용 |
| 2 | 사전 준비 미비(Ollama 서버 미연결 등) |

- **CPU 모드**에서: `--require-gpu` 없이 → PASS, `--require-gpu` → FAIL(정상).
- **PTX/CUDA 오류**: "unsupported toolchain" / "llama-server process has
  terminated" 메시지가 나오면 드라이버가 너무 오래된 것 → NVIDIA 드라이버
  업데이트 후 재시도.

## 드라이버 업데이트 후 GPU 검증 절차

```powershell
# 1) CPU 고정 해제
[Environment]::SetEnvironmentVariable('OLLAMA_LLM_LIBRARY', $null, 'User')

# 2) Ollama 재시작
Get-Process | Where-Object { $_.ProcessName -like 'ollama*' } | Stop-Process -Force
Start-Sleep 3
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve

# 3) GPU PASS/FAIL 확인
python examples\06_ollama_gpu\check_ollama_gpu.py --require-gpu
```

## 원칙

- 메인 앱(`src/`, `tests/`, `config.json`, `requirements*.txt`,
  `CMakeLists.txt`, CI) 무수정.
- `rag_core.py` 를 읽기 전용으로 재사용(색인/저장소 변경 없음).
