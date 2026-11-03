param([string]$OutputDirectory = (Join-Path $PSScriptRoot '../runs/legacy_reference_joint_development_v2_20260918'), [switch]$Once)
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'Paper04 实验进度（只读监控）'
$runPath = (Resolve-Path -LiteralPath $OutputDirectory).Path
while ($true) {
    try {
        $s = Get-Content -LiteralPath (Join-Path $runPath 'status.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $terminal = $s.status -in @('COMPLETE','STOPPED_NO_RETRY')
        $supervisor = $null
        if ($s.supervisor_pid) { $supervisor = Get-Process -Id $s.supervisor_pid -ErrorAction SilentlyContinue }
        $last = [DateTimeOffset]::FromUnixTimeMilliseconds([long]($s.updated_epoch * 1000))
        $alive = $supervisor -and ($supervisor.StartTime.ToUniversalTime() -le $last.UtcDateTime)
        $age = ([DateTimeOffset]::Now - $last).TotalSeconds
        $stateText = switch ($s.status) {
            'COMPLETE' {'完整链已结束；科学结论请查看结果分析'}
            'STOPPED_NO_RETRY' {'发生异常，已停止；不会自动重试'}
            default { if (-not $alive) {'监督器已退出：记录可能过期，并非完成'} elseif ($age -gt 90) {'进程存在，但状态更新延迟，请检查'} else {'正在运行'} }
        }
        $stageText = switch ($s.stage) {
            'PREPARE_LEARN_DEV' {'训练/开发集：提取真实特征（尚未开始训练）'}
            default {$s.stage}
        }
        if (-not $Once) { Clear-Host }
        Write-Host '=============== Paper04 实验实时监控 ===============' -ForegroundColor Cyan
        Write-Host ('界面刷新：{0}   每10秒自动刷新' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
        $color = if ($s.status -eq 'STOPPED_NO_RETRY' -or (-not $terminal -and -not $alive)) {'Red'} elseif ($age -gt 90 -and -not $terminal) {'Yellow'} else {'Green'}
        Write-Host ('状态：'+$stateText) -ForegroundColor $color
        Write-Host ('阶段：'+$stageText)
        Write-Host ''
        if ($s.total -gt 0) {
            $pct = 100.0 * $s.done / $s.total
            $filled = [Math]::Min(40,[Math]::Max(0,[int][Math]::Floor($pct * 0.4)))
            Write-Host ('[' + ('#' * $filled) + ('-' * (40-$filled)) + ']') -ForegroundColor Cyan
            Write-Host ('本阶段进度：{0:N0} / {1:N0}  ({2:N2}%)' -f $s.done,$s.total,$pct)
        } else { Write-Host '本阶段正在初始化，尚无有效进度分母。' }
        if ($s.worker.capture) {
            Write-Host ('当前流量文件：{0}' -f $s.worker.capture)
            Write-Host ('当前文件扫描包数：{0:N0} / {1:N0}' -f $s.worker.packets,$s.worker.capture_packets)
        }
        if ($s.stage_elapsed_seconds) { Write-Host ('本阶段已运行：{0:N2} 小时' -f ($s.stage_elapsed_seconds/3600)) }
        Write-Host ('进程树内存峰值：{0:N2} GiB / 12 GiB' -f ($s.peak_job_bytes/1GB))
        Write-Host ('运行目录大小：{0:N2} GiB / 16 GiB' -f ($s.output_bytes/1GB))
        Write-Host ('状态最后更新：{0}；自动重试次数：{1}' -f $last.LocalDateTime.ToString('HH:mm:ss'),$s.retries)
        if ($s.error) { Write-Host ('错误：'+$s.error) -ForegroundColor Red }
        Write-Host ''
        Write-Host '关闭此窗口仅关闭监控，不会停止后台实验。' -ForegroundColor Yellow
        Write-Host '此进度是当前阶段进度，不是整个实验链进度。'
        Write-Host ('结果目录：'+$runPath)
        if ($Once -or $terminal -or -not $alive) { break }
    } catch {
        Write-Host ('暂时无法读取状态：'+$_.Exception.Message) -ForegroundColor Yellow
        if ($Once) { throw }
    }
    Start-Sleep -Seconds 10
}