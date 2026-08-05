@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv-acestep\Scripts\python.exe"
set "RUN_DIR=%~dp0runs\feibi_unhappy_sesame4"
set "WORKSPACE_DIR=%~dp0runs"

if not exist "%PYTHON%" (
    echo [ERROR] ACE-Step Python environment not found:
    echo         %PYTHON%
    pause
    exit /b 1
)
if not exist "%RUN_DIR%\report.json" (
    echo [ERROR] Run directory or report.json not found:
    echo         %RUN_DIR%
    pause
    exit /b 1
)

echo Starting Feibi segment UI at http://127.0.0.1:7860/
echo Close this window to stop the service.
"%PYTHON%" scripts\feibi_segment_ui.py --run-dir "%RUN_DIR%" --workspace-dir "%WORKSPACE_DIR%" --host 127.0.0.1 --port 7860 --no-browser

endlocal
