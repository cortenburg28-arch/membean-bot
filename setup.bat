@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ========================================
echo   Membean Bot - Windows Einmal-Setup
echo ========================================
echo.
echo Ordner: %CD%
echo.

where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo Python nicht gefunden.
        echo Bitte Python 3.9+ installieren:
        echo   https://www.python.org/downloads/
        echo Beim Installieren "Add python.exe to PATH" ankreuzen.
        pause
        exit /b 1
    )
    set "PY=py -3"
) else (
    set "PY=python"
)

echo Python gefunden:
%PY% --version
echo.

if not exist "venv\Scripts\activate.bat" (
    echo Erstelle virtuelle Umgebung...
    %PY% -m venv venv
    if errorlevel 1 (
        echo venv konnte nicht erstellt werden.
        pause
        exit /b 1
    )
)

call "venv\Scripts\activate.bat"

echo Installiere Pakete...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo pip install fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo Installiere Chromium fuer Playwright...
playwright install chromium
if errorlevel 1 (
    echo playwright install fehlgeschlagen.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
        echo .env aus .env.example erstellt.
        echo Bitte AI_API_KEY in .env eintragen ^(von Christoph^).
    )
)

echo.
echo ========================================
echo   Setup fertig!
echo ========================================
echo.
echo Naechste Schritte:
echo   1. .env oeffnen und AI_API_KEY eintragen
echo   2. start.bat doppelklicken
echo   3. Im Menue [2] bei Membean einloggen
echo.
pause
