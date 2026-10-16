@echo off
setlocal
cd /d "%~dp0"

echo ================================
echo   PhotoSort launcher
echo ================================
echo.

REM --- 1. Find python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo Install it from https://www.python.org/downloads/ and tick
    echo "Add python.exe to PATH" during setup.
    echo.
    pause
    exit /b 1
)

REM --- 2. Create / reuse a virtual environment ---
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

REM --- 3. Install / update requirements ---
REM A marker file remembers what we last installed, so a normal launch
REM skips pip entirely. Delete .venv\.installed to force a reinstall.
if not exist ".venv\.installed" (
    echo Installing requirements ...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] pip install failed.
        pause
        exit /b 1
    )
    echo done> ".venv\.installed"
)

REM --- 4. Launch ---
echo Starting PhotoSort ...
"%VENV_PY%" -m ui.window

REM If the GUI exits with an error, keep the console open so the user
REM can see the traceback.
if errorlevel 1 (
    echo.
    echo [ERROR] PhotoSort exited with an error. See above.
    pause
)
endlocal