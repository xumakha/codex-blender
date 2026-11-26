@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m codex_blender.launcher
if errorlevel 1 pause
