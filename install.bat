@echo off
:: =============================================================================
:: MedEcho -- One-Click Installer  (Windows)
:: =============================================================================
:: Double-click this file or run it in Command Prompt / PowerShell.
::
:: What this script does:
::   1. Checks for Python 3.10+
::   2. Creates an isolated virtual environment (.venv)
::   3. Installs all Python dependencies from requirements.txt
::   4. Creates a template .env file for your API keys
::   5. Creates a launch shortcut (run.bat)
:: =============================================================================

setlocal EnableDelayedExpansion
title MedEcho Installer

:: ── Banner ─────────────────────────────────────────────────────────────────
echo.
echo  ================================================
echo    __  __          _ _____      _
echo   ^|  \/  ^| ___  __^| ^| ____^|___^| ^|__   ___
echo   ^| ^|\/^| ^|/ _ \/ _` ^|  _^| / __^| '_ \ / _ \
echo   ^| ^|  ^| ^|  __/ (_^| ^| ^|__^| (__^| ^|_^) ^|  __/
echo   ^|_^|  ^|_^|\___^|\__,_^|_____\___^|_^.__/ \___^|
echo.
echo    AI Radiology ^& Clinical Scribe  --  Installer v1.0
echo  ================================================
echo.

:: ── Step 1 -- Python version check ───────────────────────────────────────
echo [INFO]  Checking Python version...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Download from https://python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check version is 3.10+
python -c "import sys; assert sys.version_info >= (3,10), 'Need 3.10+'" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10 or higher is required.
    echo         Download from https://python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo [OK]    Found %%v

:: ── Step 2 -- Virtual environment ────────────────────────────────────────
echo [INFO]  Creating virtual environment at .venv ...
if exist ".venv\" (
    echo [WARN]  Virtual environment already exists -- skipping creation.
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK]    Virtual environment created.
)

:: ── Step 3 -- Upgrade pip ────────────────────────────────────────────────
echo [INFO]  Upgrading pip...
call .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
echo [OK]    pip is up to date.

:: ── Step 4 -- Install dependencies ───────────────────────────────────────
echo [INFO]  Installing Python dependencies (this may take a few minutes)...
call .venv\Scripts\pip.exe install --quiet -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed. Check requirements.txt.
    pause
    exit /b 1
)
echo [OK]    All dependencies installed.

:: ── Step 5 -- Create .env template ───────────────────────────────────────
if exist ".env" (
    echo [WARN]  .env file already exists -- skipping.
) else (
    echo [INFO]  Creating .env template...
    (
        echo # ──────────────────────────────────────────────────────────────────────────
        echo # MedEcho -- Environment Variables
        echo # ──────────────────────────────────────────────────────────────────────────
        echo # You can enter API keys here OR directly in the MedEcho sidebar at runtime.
        echo # Keys entered in the app sidebar take precedence over these values.
        echo.
        echo # Google Gemini API Key ^(required for cloud AI features^)
        echo # Get yours at: https://aistudio.google.com/app/apikey
        echo GEMINI_API_KEY=
        echo.
        echo # Hugging Face Token ^(required for local MedGemma / MedSigLIP weights^)
        echo # Get yours at: https://huggingface.co/settings/tokens
        echo HF_TOKEN=
        echo.
        echo # Google Cloud API Key ^(optional -- enables MedASR cloud transcription^)
        echo # Get yours at: https://console.cloud.google.com/apis/credentials
        echo GOOGLE_CLOUD_API_KEY=
    ) > .env
    echo [OK]    .env template created. Edit it with your API keys if desired.
)

:: ── Step 6 -- Create run.bat ──────────────────────────────────────────────
echo [INFO]  Creating launch script run.bat...
(
    echo @echo off
    echo :: MedEcho -- Launch Script
    echo title MedEcho
    echo cd /d "%%~dp0"
    echo :: Load .env variables
    echo if exist ".env" ^(
    echo     for /f "usebackq tokens=1,* delims==" %%%%a in ^(".env"^) do ^(
    echo         if not "%%%%a"=="" if not "%%%%a:~0,1%"=="#" set "%%%%a=%%%%b"
    echo     ^)
    echo ^)
    echo call .venv\Scripts\activate.bat
    echo echo Starting MedEcho...
    echo streamlit run app.py --server.headless false --browser.gatherUsageStats false
    echo pause
) > run.bat
echo [OK]    Launch script created: run.bat

:: ── Done ──────────────────────────────────────────────────────────────────
echo.
echo  ===================================================
echo    Installation complete!
echo  ===================================================
echo.
echo    To launch MedEcho, double-click:
echo        run.bat
echo.
echo    API keys can be entered:
echo      * In the .env file ^(persistent^)
echo      * In the MedEcho sidebar at runtime ^(session-only^)
echo.
pause
endlocal
