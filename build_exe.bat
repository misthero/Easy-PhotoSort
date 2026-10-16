@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run run.bat first to create the virtual environment.
    pause
    exit /b 1
)

set "VENV_PY=.venv\Scripts\python.exe"

echo Installing PyInstaller ...
"%VENV_PY%" -m pip install --upgrade pyinstaller

echo Building PhotoSort.exe ...
"%VENV_PY%" -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --icon assets\icon.ico ^
    --windowed ^
    --name PhotoSort ^
    --paths . ^
    ui\window.py

echo.
echo Done. The executable is at: dist\PhotoSort.exe
pause
endlocal