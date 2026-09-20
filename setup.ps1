# setup.ps1 -- cline_rag first-time setup (Windows PowerShell)
#
# Steps:
#   1) create .venv
#   2) upgrade pip
#   3) install requirements.txt       (runtime deps: none)
#   4) install requirements-dev.txt   (pytest)
#   5) verify the embedding model     (Ollama / OpenAI)
#   6) run the ingestion (index) step
#   7) MCP smoke test (spawns the server as a child process)
#   8) pytest
#   9) CMake + CTest test pack        (skippable)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1 -SkipCmake

param(
    [switch]$SkipCmake
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Sources live in src/, so put them on the import path.
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"

Write-Host "== 1/9 create .venv ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py --version

Write-Host "== 2/9 upgrade pip ==" -ForegroundColor Cyan
& $py -m pip install --upgrade pip --disable-pip-version-check --quiet

Write-Host "== 3/9 install requirements.txt ==" -ForegroundColor Cyan
& $py -m pip install -r requirements.txt --disable-pip-version-check --quiet
if ($LASTEXITCODE -ne 0) { throw "requirements.txt install failed" }

Write-Host "== 4/9 install requirements-dev.txt (pytest) ==" -ForegroundColor Cyan
& $py -m pip install -r requirements-dev.txt --disable-pip-version-check --quiet
if ($LASTEXITCODE -ne 0) { throw "requirements-dev.txt install failed" }

Write-Host "== 5/9 verify embedding model ==" -ForegroundColor Cyan
$provider = (& $py -c "import rag_core as c; print(c.load_config()['embedding']['provider'])").Trim()
if ($provider -eq "ollama") {
    $model = (& $py -c "import rag_core as c; print(c.load_config()['embedding']['ollama']['model'])").Trim()
    $have = (ollama list 2>$null) -match [regex]::Escape($model)
    if (-not $have) {
        Write-Host "  pulling '$model' ..." -ForegroundColor Yellow
        ollama pull $model
    } else {
        Write-Host "  '$model' present"
    }
} elseif ($provider -eq "openai") {
    if (-not $env:OPENAI_API_KEY) {
        throw "embedding provider is openai but OPENAI_API_KEY is not set"
    }
    Write-Host "  OPENAI_API_KEY detected"
}

Write-Host "== 6/9 index documents ==" -ForegroundColor Cyan
& $py src\ingest.py --reset
if ($LASTEXITCODE -ne 0) { throw "indexing failed" }

Write-Host "== 7/9 MCP smoke test ==" -ForegroundColor Cyan
& $py smoke_mcp.py
if ($LASTEXITCODE -ne 0) { throw "MCP smoke test failed" }

Write-Host "== 8/9 pytest ==" -ForegroundColor Cyan
& $py -m pytest tests -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

if ($SkipCmake) {
    Write-Host "== 9/9 CMake test pack (skipped) ==" -ForegroundColor DarkGray
} else {
    Write-Host "== 9/9 CMake + CTest test pack ==" -ForegroundColor Cyan
    cmake --preset default
    if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }
    ctest --preset default
    if ($LASTEXITCODE -ne 0) { throw "ctest failed" }
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Register this in your Cline MCP settings:"
Write-Host "  command : $py"
Write-Host "  args    : $(Join-Path $PSScriptRoot 'src\rag_server.py')"