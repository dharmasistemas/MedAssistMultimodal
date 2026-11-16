# Verifica o baseline offline sem iniciar serviços ou baixar dependências.
[CmdletBinding()]
param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousPythonPath = $env:PYTHONPATH
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    & $Python -B -m medassistmultimodal
    if ($LASTEXITCODE -ne 0) { throw 'Falha na verificação do baseline offline.' }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
