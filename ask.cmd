@echo off
REM ask.cmd -- cmd.exe / 더블클릭에서도 쓸 수 있는 질의 런처.
REM 내부적으로 ask.ps1 을 호출한다(.venv 의 python 을 자동으로 찾아 쓴다).
REM 사용: ask.cmd "연차는 반차 단위로도 신청할 수 있니?"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ask.ps1" %*
