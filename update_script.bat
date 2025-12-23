@echo off
REM Script to pull the latest version of tg_downloader.py from GitHub (Windows)
REM This can be used as part of a scheduled task to ensure you always have the latest version

set REPO_URL=https://raw.githubusercontent.com/idMdev/tg-downloader/main/tg_downloader.py
set SCRIPT_NAME=tg_downloader.py
set BACKUP_NAME=tg_downloader.py.backup

echo Telegram Downloader Auto-Update Script
echo ========================================

REM Check if script exists and create backup
if exist %SCRIPT_NAME% (
    echo Creating backup of existing script...
    copy %SCRIPT_NAME% %BACKUP_NAME% >nul
)

REM Download the latest version using PowerShell
echo Downloading latest version from GitHub...
powershell -Command "try { Invoke-WebRequest -Uri '%REPO_URL%' -OutFile '%SCRIPT_NAME%' -UseBasicParsing; Write-Host 'Successfully updated %SCRIPT_NAME%' -ForegroundColor Green; exit 0 } catch { Write-Host 'Failed to download latest version' -ForegroundColor Red; exit 1 }"

if %ERRORLEVEL% NEQ 0 (
    REM Restore backup if download failed
    if exist %BACKUP_NAME% (
        echo Restoring backup...
        move /Y %BACKUP_NAME% %SCRIPT_NAME% >nul
    )
    exit /b 1
)

echo.
echo You can now run: python %SCRIPT_NAME% --channel @yourchannel
pause
