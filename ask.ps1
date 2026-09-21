# ask.ps1 -- 프로젝트 루트에서 바로 질문하는 런처.
#
# src\ask.py 를 항상 .venv 의 python 으로 실행해주는 얇은 래퍼다.
# "python src\ask.py ..." 처럼 시스템 python 으로 잘못 실행해서 발생하는
# ModuleNotFoundError(langchain_community 등)를 원천적으로 피하기 위한 것이다.
#
# 사용:
#   .\ask.ps1 "연차는 반차 단위로도 신청할 수 있니?"
#   .\ask.ps1 "청크 크기" --mode vector --top-k 5
#   .\ask.ps1 "청크 크기" --json

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# PowerShell 은 외부(네이티브) 프로세스의 stdout 을 파이프/리다이렉션으로 받을 때
# $OutputEncoding 변수를 기준으로 바이트를 텍스트로 해석한다. 이 값은 콘솔
# 코드페이지(chcp)와 별개로 세션 시작 시 고정되며, 보통 한글 Windows 에서는
# UTF-8 이 아니다. 그래서 "chcp 65001" 을 해도 파이프/리다이렉션 결과의 한글이
# 깨지는 경우가 있다. 이 스크립트 안에서 강제로 UTF-8 로 맞춰서, 화면 출력이든
# 파일로 리다이렉션(`.\ask.ps1 "질문" > out.txt`)이든 항상 한글이 정상으로
# 나오게 한다.
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = "utf-8"

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "오류: 가상환경(.venv)이 없습니다." -ForegroundColor Red
    Write-Host "먼저 아래 명령으로 설치하세요:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\setup.ps1"
    exit 1
}

if (-not $Args -or $Args.Count -eq 0) {
    Write-Host "사용법: .\ask.ps1 `"질문`" [--top-k N] [--mode hybrid|vector|keyword] [--json]"
    exit 1
}

& $venvPython (Join-Path $PSScriptRoot "src\ask.py") @Args
exit $LASTEXITCODE
