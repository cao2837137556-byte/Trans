#!/bin/bash
# CKBW seed-27 live monitor.  Usage: bash issue27ckbw_watch_seed27.sh <job_id>
# Refreshes every INTERVAL seconds.  Besides queue/phase state it computes the
# real CPU consumption between consecutive samples, so a "RUNNING but hung"
# job is caught (the silent-stall failure mode that once burned 9 hours).
set -u
JOB=${1:?usage: bash issue27ckbw_watch_seed27.sh <job_id>}
BASE=${CKBW_BASE:-/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline}
ROOT="$BASE/runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_${JOB}"
INTERVAL=${CKBW_WATCH_INTERVAL:-30}

t2s() {
  local t=$1 d=0 h=0 m=0 s=0 a="" b="" c=""
  [[ "$t" == *-* ]] && { d=${t%%-*}; t=${t#*-}; }
  IFS=: read -r a b c <<< "$t"
  if [[ -n "$c" ]]; then h=$a; m=$b; s=$c; else m=${a:-0}; s=${b:-0}; fi
  printf '%d' $(( 10#${d:-0}*86400 + 10#${h:-0}*3600 + 10#${m:-0}*60 + 10#${s:-0} ))
}

prev_total=""
prev_elapsed=""
low_streak=0

while true; do
  clear
  echo "=== CKBW seed-27 monitor  job=$JOB  $(date '+%F %T')  (Ctrl+C 退出，不影响作业) ==="
  qline=$(squeue -h -j "$JOB" -o '%T|%M|%L|%R' 2>/dev/null | head -1)
  state="ENDED"; elapsed_s=0; left="-"; node="-"
  if [[ -n "$qline" ]]; then
    state=${qline%%|*}; rest=${qline#*|}
    elapsed_str=${rest%%|*}; rest=${rest#*|}
    left=${rest%%|*}; node=${rest#*|}
    elapsed_s=$(t2s "$elapsed_str")
    if [[ "$state" == "PENDING" ]]; then
      echo "状态: 排队中 (PENDING)  已等: $elapsed_str  原因: $node"
    else
      echo "状态: $state  已运行: $elapsed_str  剩余上限: $left  节点: $node"
    fi
  else
    echo "状态: 已离开队列（结束或完成）"
  fi

  echo "--- 阶段 ---"
  if [[ -s "$ROOT/current_phase.txt" ]]; then
    cat "$ROOT/current_phase.txt"
  else
    echo "(阶段文件尚未创建：还在排队或刚启动)"
  fi

  if [[ -s "$ROOT/formal_stdout.log" ]]; then
    echo "--- 训练日志: $(wc -l < "$ROOT/formal_stdout.log") 行，最后更新 $(date -r "$ROOT/formal_stdout.log" '+%H:%M:%S') ---"
    echo "    （训练阶段数小时不更新属正常，存活与否看下面的 CPU 判定）"
  fi

  hb=$(grep 'CKBW_PROGRESS' "$BASE/runs/issue27ckbw_amd_${JOB}.out" 2>/dev/null | tail -1)
  if [[ -n "$hb" ]]; then
    echo "--- Slurm 心跳 ---"
    echo "$hb"
  fi

  if [[ "$state" == "RUNNING" ]]; then
    ave_str=$(sstat -j "${JOB}.batch" -P -n --format=AveCPU 2>/dev/null | head -1)
    if [[ -n "$ave_str" ]]; then
      ave_s=$(t2s "$ave_str")
      total=$((ave_s * elapsed_s))
      if [[ -n "$prev_total" && "$elapsed_s" -gt "$prev_elapsed" ]]; then
        rate=$(( (total - prev_total) / (elapsed_s - prev_elapsed) ))
        echo "--- CPU 判定 ---"
        if [[ "$rate" -ge 3 ]]; then
          echo "计算健康：约 $rate 核正在满负荷训练"
          low_streak=0
        elif [[ "$rate" -ge 1 ]]; then
          echo "低占用（约 $rate 核）：数据加载/读写阶段属正常"
          low_streak=0
        else
          if [[ "$elapsed_s" -gt 600 ]]; then
            low_streak=$((low_streak + 1))
            echo "CPU 几乎为零（约 $rate 核），已连续 $low_streak 次"
            if [[ "$low_streak" -ge 6 ]]; then
              echo "!!! 疑似卡死：RUNNING 但已 $((low_streak * INTERVAL / 60)) 分钟几乎无 CPU 消耗 !!!"
              echo "请把本屏内容和 $ROOT/job_failure.txt（若存在）发给 Kimi/Codex。"
            fi
          else
            echo "启动初期（约 $rate 核），暂不做卡死判定"
          fi
        fi
      else
        echo "--- CPU 判定 ---"
        echo "取样中（下一轮刷新出判定）"
      fi
      prev_total=$total
      prev_elapsed=$elapsed_s
    else
      echo "--- CPU 判定 ---"
      echo "sstat 暂无数据（步骤刚启动）"
    fi
  fi

  if [[ -s "$ROOT/job_failure.txt" ]]; then
    echo
    echo "!!! 作业失败 !!!"
    cat "$ROOT/job_failure.txt"
    exit 4
  fi

  phase_now=""
  [[ -s "$ROOT/current_phase.txt" ]] && \
    phase_now=$(awk -F= '$1=="phase" {print $2; exit}' "$ROOT/current_phase.txt")
  if [[ "$phase_now" == "complete" ]]; then
    echo
    echo "=== 作业完成 ==="
    grep -o '"decision": *"[^"]*"' "$ROOT/ckbw_single_seed_go_no_go.json" 2>/dev/null | head -1
    echo "pullback: $BASE/runs/issue27ckbw_seed27_amd_${JOB}_pullback.tar.gz"
    exit 0
  fi

  if [[ "$state" == "ENDED" && "$phase_now" != "complete" ]]; then
    echo
    echo "作业已结束但未到达 complete 阶段，记账信息："
    sacct -j "$JOB" -X --format=JobID,State,ExitCode,Elapsed 2>/dev/null || true
    echo "请把本屏内容发给 Kimi/Codex。"
    exit 3
  fi

  sleep "$INTERVAL"
done
