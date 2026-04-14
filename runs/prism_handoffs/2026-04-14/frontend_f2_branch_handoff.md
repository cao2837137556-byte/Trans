# Frontend-F2 Branch Handoff

## 1. 这条分支是干什么的

- 分支名：`codex/frontend-f2`
- 目录：`worktrees/kitnet-frontend-f2`
- 目标：为当前 stronger-OOD 异常检测项目探索“前端表达重构”路线，而不是继续只在旧 `100D` 平面表示上做后端修补。

## 2. 它和主线什么关系

- 主线分支：`codex/exp-mainline`
- 主线职责：维护当前论文主叙事、稳定 strongest candidate、保留已经验证过的主实验代码。
- `frontend-f2` 职责：高风险前端重构支线。
- 原则：`frontend-f2` 可以失败，但不能污染主线；只有明确有效的代码和结论才合并回 `codex/exp-mainline`。

## 3. 当前做到哪一步

- 已经完成真实数据的 Frontend-F2 结构化缓存抽取：
  - ID：`7-6`
  - OOD benign：`4-1`
  - attack：`34-1`
- 已实现第一版真实结构化 tokenizer：
  - `repo/ood/frontend_f2_structured_tokenizer_v1.py`
- 已实现第一版 contrast-token 前端：
  - `repo/ood/frontend_f2_contrast_tokenizer_v1.py`
- 已完成 smoke：
  - `runs/frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14/summary.md`

## 4. 已经失败过什么

- 单纯把原 `100D` 重新排成更“像 Transformer 输入”的结构，收益有限。
- `frontend_f2_structured_tokenizer_v1` 证明真实结构化前端链路可运行，但 detection 很低：
  - 最好大约在 `alarm ~ 0.012 / det ~ 0.20`
- 结论：仅做“结构重排”不够，攻击信号没有被有效前置表达出来。

## 5. 当前最重要的实证结论

- `frontend_f2_contrast_tokenizer_v1` 首次把“短时相对长时的异常增量”直接做成输入 token。
- 这条线相比前一版 structured tokenizer，已经把 detection 从约 `0.20` 拉到约 `0.30`，说明方向有真实信号。
- 但当前结果仍不足以挑战主线或 dA：
  - 最佳 token-MLP 点大约为 `alarm 0.0719 / det 0.2995`
  - 最佳 transformer 点大约为 `alarm 0.1328 / det 0.2858`
- 当前判断：
  - 方向认可
  - 当前实现不认可

## 6. 下一步打算做什么

- 优先做 `frontend_f2_contrast_tokenizer_v1_1`
- 核心不是继续美化旧 `100D`，而是进一步强化真正有物理意义的前端增量信号。
- 下一步重点：
  - 更强调 `delta_global` 和 `delta_mid`
  - 弱化或移除容易稀释边界的 `abs_short`
  - 保留 `HH/HpHp` 的 family focus 先验
  - 保持最小变量控制，不同时大改模型和 scorer

## 7. 必看的文件列表

- 总实验地图：
  - `runs/master_experiment_map_v1.md`
- F2 设计说明：
  - `runs/prism_handoffs/2026-04-13/frontend_f2_controlled_redesign_spec_2026-04-13.md`
- 当前 smoke 结果：
  - `runs/frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14/summary.md`
- 当前核心代码：
  - `repo/ood/frontend_f2_contrast_tokenizer_v1.py`
  - `repo/ood/frontend_f2_structured_tokenizer_v1.py`
  - `repo/ood/prepare_frontend_f2_crosscapture_sources.py`
  - `repo/ood/prepare_frontend_f2_attack_source.py`
  - `repo/ood/kitsune_frontend_original_extract.py`

## 8. 新对话开场建议

把下面这段直接发给新对话：

```text
这个对话绑定的是 `codex/frontend-f2` worktree，请先理解背景，不要立刻改代码。

先读：
1. runs/prism_handoffs/2026-04-14/frontend_f2_branch_handoff.md
2. runs/master_experiment_map_v1.md
3. runs/prism_handoffs/2026-04-13/frontend_f2_controlled_redesign_spec_2026-04-13.md
4. runs/frontend_f2_contrast_tokenizer_v1_smoke_2026-04-14/summary.md
5. repo/ood/frontend_f2_contrast_tokenizer_v1.py

先用 5-10 条总结：
- 这条分支的目标
- 它和主线的关系
- 当前最强 smoke 结果
- 当前最关键的瓶颈
- 下一步最合理的 v1.1 改动

总结后再等我给具体任务。
```
