@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Check venv python...
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv\Scripts\python.exe not found
    echo Create venv from this PC, e.g.  py -3.10 -m venv .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import sys" 1>nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: .venv points to Python that does not exist on this PC.
    echo Common cause: project was copied from another user machine ^(see .venv\pyvenv.cfg "home"^).
    echo Fix: delete the .venv folder, then in this project root run:
    echo   py -3.10 -m venv .venv
    echo   OR   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -U pip
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo Then run this build_onefile.bat again.
    echo.
    pause
    exit /b 1
)

echo [1.5/4] pip install -r requirements.txt ^(if needed^)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install -r requirements.txt failed
    pause
    exit /b 1
)

echo [2/4] Check PyInstaller...
".venv\Scripts\python.exe" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo [2.5/4] Close old AutoPhote.exe if running...
taskkill /f /im AutoPhote.exe >nul 2>&1
if exist "dist\AutoPhote.exe" (
    del /f /q "dist\AutoPhote.exe" >nul 2>&1
)

echo [3/4] Build onefile EXE...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onefile --name AutoPhote main.py
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo Build completed: dist\AutoPhote.exe
pause
endlocal
