# Worktree SOP（固定工作树规则）

## 1) 目录与分支

- 主仓库（稳定主线）
  - 路径：`D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master`
  - 分支：`main`

- 实验工作树（长期）
  - 路径：`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`
  - 分支：`codex/exp-mainline`

- 论文交接工作树（长期）
  - 路径：`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-paper-handoff`
  - 分支：`codex/paper-handoff`

## 2) 使用规则

- `main`：只合并“已确认可复现”的代码和文档，不直接做高风险实验开发。
- `codex/exp-mainline`：只做实验脚本与评估改动，run-tag 建议带 `_exp`。
- `codex/paper-handoff`：只整理图表、summary、handoff 文档，避免混入实验临时代码。

## 3) 结果与文档放置

- 长期固定论文交接目录：`runs/prism_handoffs/YYYY-MM-DD/`
- 主线地图：`runs/master_experiment_map_v1.md`
- 快速文件导航：`runs/quick_file_map_2026-03-30.md`

## 4) 常用命令

```bash
# 查看工作树
git worktree list

# 进入实验工作树
cd D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline

# 进入论文交接工作树
cd D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-paper-handoff

# 若未来不再使用某工作树
git worktree remove D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline
git worktree remove D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-paper-handoff
```

## 5) 注意

- 当前 `.gitignore` 已默认忽略大数据与大部分 runs 产物，只保留关键 handoff 文档。
- 若要提交某个新的结果文档，请确认路径在 `runs/prism_handoffs/` 或手动调整 `.gitignore`。
