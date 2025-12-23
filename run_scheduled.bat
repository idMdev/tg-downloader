@echo off
REM Example runner script for scheduled execution (Windows)
REM This script updates the downloader and runs it with your preferred settings

cd /d %~dp0

echo Updating to latest version...
call update_script.bat

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Running downloader...
    
    REM Run the downloader with your settings
    REM Modify the parameters below according to your needs
    
    python tg_downloader.py ^
        --channel @yourchannel ^
        --types pdf,jpg,png,mp4 ^
        --dest ./downloads ^
        --max-size 100 ^
        --limit 100
    
    if %ERRORLEVEL% EQU 0 (
        echo Download completed successfully at %date% %time%
    ) else (
        echo Download failed at %date% %time%
        exit /b 1
    )
) else (
    echo Update failed. Skipping download.
    exit /b 1
)
