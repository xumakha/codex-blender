$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Run python -m venv .venv and install the project first.'
}
& codex.cmd mcp add blender -- $pythonPath -m codex_blender.server
if ($LASTEXITCODE -ne 0) { throw 'Could not register the MCP server.' }
Write-Host 'Blender MCP registered. Restart Codex to load the tools.'
