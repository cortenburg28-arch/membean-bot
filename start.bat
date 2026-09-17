@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if not exist "main.py" (
    echo Fehler: main.py nicht gefunden.
    echo Ordner: %CD%
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo Erstes Mal auf Windows? Bitte zuerst setup.bat ausfuehren.
    echo Ordner: %CD%
    echo.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"
python main.py start
if errorlevel 1 (
    echo.
    echo Programm beendet mit Fehler.
    pause
)
