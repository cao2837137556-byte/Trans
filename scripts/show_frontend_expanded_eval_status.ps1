$ErrorActionPreference = 'Stop'
$evalRoot = Split-Path -Parent $PSScriptRoot
$evalOut = Join-Path $evalRoot 'runs/frontend_expanded_eval_v1_20260910'
if (-not (Test-Path -LiteralPath $evalOut)) { Write-Output '尚未启动扩大测试'; exit 0 }
$evalTerminal = Join-Path $evalOut 'supervisor_terminal.json'
$evalProgress = Join-Path $evalOut 'progress.json'
$evalPath = if (Test-Path -LiteralPath $evalTerminal) { $evalTerminal } else { $evalProgress }
Get-Content -LiteralPath $evalPath -Raw | ConvertFrom-Json | Format-List
Write-Output ('状态文件：' + (Join-Path $evalOut 'status.md'))
if (Test-Path -LiteralPath (Join-Path $evalOut 'result.md')) { Write-Output ('结果文件：' + (Join-Path $evalOut 'result.md')) }
