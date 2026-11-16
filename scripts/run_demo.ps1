# A demonstração multimodal ainda depende dos próximos incrementos.
[CmdletBinding()]
param([string]$Python = 'python')
& (Join-Path $PSScriptRoot 'start_medassistmultimodal.ps1') -Python $Python
