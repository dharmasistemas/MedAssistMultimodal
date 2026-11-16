# Dot-source this script to retain Conda functions in the interactive session.
param(
    [string]$CondaExe = (Join-Path $env:USERPROFILE 'miniconda3/Scripts/conda.exe')
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $CondaExe -PathType Leaf)) {
    throw "Conda executable not found: $CondaExe. Pass -CondaExe with its path."
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$condaHook = & $CondaExe 'shell.powershell' 'hook' | Out-String
if ($LASTEXITCODE -ne 0) { throw 'Conda PowerShell initialization failed.' }
Invoke-Expression $condaHook
conda activate medassistmultimodal
if ($LASTEXITCODE -ne 0 -or $env:CONDA_DEFAULT_ENV -ne 'medassistmultimodal') {
    throw 'Could not activate the medassistmultimodal environment.'
}
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath (Join-Path $env:CONDA_PREFIX 'python.exe'))) {
    Write-Warning 'Environment activated, but Python is not installed in it yet.'
}
