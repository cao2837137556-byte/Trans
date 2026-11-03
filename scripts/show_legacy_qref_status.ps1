param([Parameter(Mandatory=$true)][string]$RunDir)
$ErrorActionPreference = 'Stop'
$entries = @(Get-ChildItem -LiteralPath (Join-Path $RunDir 'progress') -Filter '*.json' -File | Sort-Object Name)
if ($entries.Count -eq 0) { Write-Output 'NOT_STARTED'; exit 0 }
$s = Get-Content -LiteralPath $entries[-1].FullName -Raw | ConvertFrom-Json
$s | Select-Object status,stage,completed_updates,total_updates,elapsed_seconds,error,retries,heldout_opened | Format-List
Write-Output 'RUNNING is the last recorded state, not proof a disconnected process is still alive.'
