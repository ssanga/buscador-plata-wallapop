# Ejecuta el batch nocturno y guarda el log del día. Lo invoca el Programador de tareas.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force "$root\logs" | Out-Null
$log = "$root\logs\batch_$(Get-Date -Format yyyy-MM-dd).log"
$env:PYTHONIOENCODING = "utf-8"
$python = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { "python" }
& $python main.py batch *>> $log
exit $LASTEXITCODE
