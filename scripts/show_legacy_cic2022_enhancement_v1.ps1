param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$enhancementRoot = Split-Path -Parent $PSScriptRoot
$enhancementPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
& $enhancementPython -B (Join-Path $enhancementRoot 'repo/ood/legacy_cic2022_enhancement_control_v1.py') status --out $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'Unable to read status; do not restart the experiment.' }
