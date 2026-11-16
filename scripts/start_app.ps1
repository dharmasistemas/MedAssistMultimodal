[CmdletBinding()]
param([string]$Python = 'python', [string]$Database, [switch]$Demo)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousPythonPath = $env:PYTHONPATH
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    if ($Demo) {
        if ($Database) { throw 'Use -Demo ou -Database, separadamente.' }
        $manifestText = & $Python -B -m medassistmultimodal.prepare_demo
        if ($LASTEXITCODE -ne 0) { throw 'Falha na preparação dos exemplos sintéticos.' }
        $manifest = ($manifestText -join "`n") | ConvertFrom-Json
        $Database = $manifest.database
        Write-Host "Nova base sintética: $Database"
    }
    if ($Database) {
        & $Python -B -m medassistmultimodal.desktop_multimodal --database $Database
    } else {
        & $Python -B -m medassistmultimodal.desktop_multimodal
    }
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao executar o aplicativo.' }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
