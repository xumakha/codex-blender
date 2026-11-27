@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-studio.ps1"
if errorlevel 1 (
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m codex_blender.launcher
if errorlevel 1 pause
