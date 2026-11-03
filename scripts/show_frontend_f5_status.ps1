param([switch]$Once)
$ErrorActionPreference = 'Stop'
$f5Output = Join-Path $PSScriptRoot '../runs/frontend_f5_unified_student_v1_20260906_local'
function Read-F5Json([string]$Name) {
    $f5Path = Join-Path $f5Output $Name
    if (Test-Path -LiteralPath $f5Path) { Get-Content -LiteralPath $f5Path -Raw | ConvertFrom-Json }
}
do {
    if (-not $Once) { Clear-Host }
    Write-Host 'F5 训练状态（只读）' -ForegroundColor Cyan
    Write-Host "更新时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    try {
        $f5Terminal = Read-F5Json 'training/terminal.json'
        $f5Failure = Read-F5Json 'engineering_failure.json'
        $f5Resource = Read-F5Json 'resource_stop.json'
        $f5Time = Read-F5Json 'training/time.json'
        $f5Heartbeat = Read-F5Json 'heartbeat.json'
        $f5Lock = Read-F5Json 'run.lock'
        $f5Live = $null
        if ($f5Lock) { $f5Live = Get-Process -Id $f5Lock.pid -ErrorAction SilentlyContinue }
        Write-Host ''
        if ($f5Failure) {
            Write-Host '状态：异常停止，需要检查；不要重新启动训练。' -ForegroundColor Red
            Write-Host $f5Failure.error
        } elseif ($f5Resource) {
            Write-Host '状态：资源上限停止；不能作为科学通过结果。' -ForegroundColor Yellow
            Write-Host $f5Resource.error
        } elseif ($f5Terminal.complete) {
            if ($f5Terminal.status -eq 'F5_NO_ELIGIBLE_CHECKPOINT') {
                Write-Host '状态：训练已结束，未通过冻结门槛。' -ForegroundColor Yellow
                Write-Host '没有合格检查点；不是程序崩溃，不能进入 K 评估。'
            } else {
                Write-Host '状态：训练已结束，已选定检查点。' -ForegroundColor Green
                Write-Host '这不是完整方案 PASS；K 评估需要单独授权。'
            }
            Write-Host "完成轮数：$($f5Terminal.epochs)；优化器步数：$($f5Terminal.steps)"
            Write-Host "结果代码：$($f5Terminal.status)"
            if ($f5Live) { Write-Host '进程仍在收尾，请勿重复启动。' }
        } elseif ($f5Live) {
            Write-Host "状态：进程运行中（PID $($f5Lock.pid)）" -ForegroundColor Green
            Write-Host "最近心跳：第 $($f5Heartbeat.epoch) 轮；上下文进度 $($f5Heartbeat.batch_cursor)/4984"
            if ($f5Heartbeat.utc) {
                $f5Age = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [double]$f5Heartbeat.utc
                Write-Host "心跳距今：$([math]::Round($f5Age)) 秒"
                if ($f5Age -gt 180) { Write-Host '心跳较旧，需要检查；进程存在不保证正在推进。' -ForegroundColor Yellow }
            }
        } elseif ($f5Lock -or $f5Time) {
            Write-Host '状态：无存活进程且缺少结束记录，需要检查。不要重新初始化。' -ForegroundColor Red
        } else { Write-Host '状态：尚未启动训练。' }
        if ($f5Time) { Write-Host "累计训练用时：$([math]::Round($f5Time.elapsed / 60, 2)) 分钟" }
        $f5Epochs = @(Read-F5Json 'training/epoch_ledger.json')
        if ($f5Epochs.Count -gt 0 -and $f5Epochs[-1]) {
            $f5Last = $f5Epochs[-1]
            Write-Host "最近完成轮次：$($f5Last.epoch)；本轮合格：$($f5Last.eligible)"
            Write-Host "训练侧保护违例：$($f5Last.train_protected_flips)"
        }
    } catch { Write-Host "状态读取暂时失败，下次刷新重试：$_" -ForegroundColor Yellow }
    Write-Host ''
    Write-Host '每 15 秒自动刷新。关闭本窗口不会停止训练。'
    Write-Host '本窗口不启动训练、不修改数据、不执行评估。'
    if (-not $Once) { Start-Sleep -Seconds 15 }
} while (-not $Once)
