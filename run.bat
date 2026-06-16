@echo off
cd /d "%~dp0"
title TrackRip - Music Downloader

echo ========================================
echo   TrackRip - Music Downloader
echo ========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH
    echo Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import sys; print(f'Python {sys.version}')"
echo.

if not exist "venv" (
    echo [*] First launch - creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [*] Installing dependencies...
    pip install --quiet flask yt-dlp
    echo [OK] Dependencies installed.
    echo.
) else (
    call venv\Scripts\activate.bat
)

:: Setup ffmpeg
python setup_ffmpeg.py
if %errorlevel% neq 0 (
    echo [!] ffmpeg setup failed - downloads will work without thumbnails
)

:: Start slskd if found and not running
tasklist /FI "IMAGENAME eq slskd.exe" 2>nul | find "slskd.exe" >nul
if %errorlevel% neq 0 (
    if exist "slskd\slskd.exe" (
        echo [*] Starting slskd...
        start "" /B /MIN slskd\slskd.exe
        timeout /t 3 /nobreak >nul
        echo [OK] slskd started on http://localhost:5030
    )
)

echo.
echo [*] Server: http://localhost:8844
echo [*] Press Ctrl+C to stop
echo.
python -u server.py

echo.
echo Server stopped.
taskkill /F /IM slskd.exe >nul 2>&1
pause
