$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host 'Creating Python environment...'
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { & $python.Source -m venv .venv }
    else { & py -3 -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required. Install Python and run start-studio.cmd again.' }
}
& $pythonPath -c "import importlib.util, sys; sys.exit(0 if sys.version_info >= (3,11) and all(importlib.util.find_spec(name) for name in ['mcp','pydantic','imageio_ffmpeg','psutil','starlette','uvicorn','multipart','edge_tts','dotenv']) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing Studio dependencies...'
    & $pythonPath -m pip --use-feature=truststore install uv
    if ($LASTEXITCODE -ne 0) { throw 'Could not install uv. Check the Internet connection and certificate configuration.' }
    & $pythonPath -m uv --system-certs pip install --python $pythonPath -e .
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. See the error above and run start-studio.cmd again.' }
}
& $pythonPath -c @'
import sys
from codex_blender.config import blender_command
try:
    blender_command()
except (ValueError, RuntimeError):
    sys.exit(1)
'@
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Blender not found. Installing the headless Blender runtime...'
    & $pythonPath -m pip --use-feature=truststore install uv
    if ($LASTEXITCODE -ne 0) { throw 'Could not install uv.' }
    & $pythonPath -m uv --system-certs pip install --python $pythonPath bpy
    if ($LASTEXITCODE -ne 0) { throw 'Install Blender and set BLENDER_PATH, then run start-studio.cmd again.' }
}
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'outputs') | Out-Null
