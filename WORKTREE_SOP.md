# Worktree / Branch Workflow SOP

## 1. 这份文件是干什么的

- 这份文件固定本项目后续的工作流程。
- 目标是把以下几件事彻底分开：
  - 主线推进
  - 新支线派生
  - 支线实验
  - 代码同步到 GitHub
  - 支线成果回收进主线

## 2. 项目当前固定结构

### 主仓

- 目录：`D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master`
- 分支：`main`
- 作用：最稳定的本地基座，不直接承担高风险实验。

### A 线主工作树

- 目录：`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline`
- 分支：`codex/exp-mainline`
- 作用：当前主实验线、论文主叙事代码线。

### B 线示例工作树

- 目录：`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2`
- 分支：`codex/frontend-f2`
- 作用：前端重构支线；失败也不污染主线。

## 3. 对话角色固定规则

### 旧长对话

- 作用：总控、论文叙事、路线判断、历史背景解释。
- 不再负责派生 worktree，也不负责具体支线开发。

### A 线主树下的“主线控制”对话

- 目录绑定：`kitnet-exp-mainline`
- 只负责：
  - 看主线 git 状态
  - 决定是否开新支线
  - 派生新 worktree
  - merge / cherry-pick 支线成果回主线
  - push 主线

### A 线主树下的“主线实验推进”对话

- 目录绑定：`kitnet-exp-mainline`
- 只负责：
  - A 线实验推进
  - A 线代码修改
  - A 线结果判断

### 每条支线的专属对话

- 目录绑定：该支线 worktree
- 只负责：
  - 本支线实验
  - 本支线代码修改
  - 本支线 handoff 更新

## 4. 什么时候要开新分支 / 新 worktree

只有一种情况需要开新分支：

- 你要开一条**可能失败、且不想污染当前线**的新实验方向。

例如：

- 前端重构
- 蒸馏新路线
- 第二数据集快速自证
- runtime / deployability 独立补实验

### 不需要开新分支的情况

- 继续做当前 A 线
- 继续做当前 B 线
- 只是当前路线里的 v1.1 / v1.2 递进

这种情况直接在当前 worktree 里继续做即可。

## 5. 新支线默认从哪里开

### 默认规则

- 新方向默认从 A 线 `codex/exp-mainline` 开。

### 只有在下面情况，才从某条支线继续开子支线

- 新方向明确依赖那条支线的已有改动。

例如：

- `frontend-f2-delta-only` 明显依赖 `frontend-f2`
- 这时可以从 `codex/frontend-f2` 再派生

## 6. 新支线的标准创建方式

在 `kitnet-exp-mainline` 的“主线控制”对话里执行：

```powershell
git worktree add -b codex/<branch-name> D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-<branch-name> codex/exp-mainline
```

例如：

```powershell
git worktree add -b codex/frontend-f2 D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2 codex/exp-mainline
```

含义：

- 新建一个本地目录
- 新建一个分支
- 用主线当前代码作为起点

## 7. 每条支线必须维护什么文件

### 总地图

- 文件：`runs/master_experiment_map_v1.md`
- 作用：记录整个项目总时间线和关键裁决

### 分支入口 handoff

- 路径模板：`runs/prism_handoffs/YYYY-MM-DD/<branch>_handoff.md`
- 作用：让新对话快速理解该支线背景

每条分支 handoff 至少写清：

1. 这条分支是干什么的
2. 它和主线什么关系
3. 当前做到哪一步
4. 已经失败过什么
5. 当前最重要的结论
6. 下一步打算做什么
7. 必看的文件列表

## 8. 每条线日常开发时的 git 逻辑

### 在某条线里改完代码后

在该 worktree 目录里执行：

```powershell
git add repo runs\master_experiment_map_v1.md runs\prism_handoffs
git commit -m "update experiment code"
git push
```

含义：

- `git add`：把要提交的代码和关键文档加入本次提交
- `git commit`：把当前这条线的代码状态固定到本地 git 历史
- `git push`：把这条线的 commit 同步到 GitHub

### 重要说明

- 在 B 线里执行 `commit + push`，只会更新 B 线分支
- 不会自动回到 A 线
- 不会自动合并回主线

## 9. 实验做完后，怎么收回主线

### 第一步：先把支线自己固定好

在支线目录里：

```powershell
git add repo runs\master_experiment_map_v1.md runs\prism_handoffs
git commit -m "finalize branch result"
git push
```

### 第二步：回主线控制对话

进入 `kitnet-exp-mainline`

### 第三步：决定回收方式

#### 整条支线都值得保留

```powershell
git merge codex/<branch-name>
git push
```

#### 只有部分提交值得保留

```powershell
git cherry-pick <commit-id>
git push
```

## 10. GitHub 在这里承担什么角色

GitHub 主要承担：

- 代码远端同步
- 网页端 GPT / Gemini 可读入口
- 关键 handoff 文档共享

GitHub 不承担：

- 所有大体积实验产物存储
- 所有 checkpoint / bundle / 大量 csv 的长期归档

### 原则

- 代码、关键 handoff、关键总表要 push
- 大型运行产物以本地 / 超算 / 手工打包为主

## 11. 以后固定使用的最短规则

### 规则 1

- 新方向才开新分支 / 新 worktree

### 规则 2

- 继续当前方向就在当前 worktree 里做，不要乱开分支

### 规则 3

- 每条支线必须维护 branch handoff

### 规则 4

- 每个稳定节点都 `commit + push`

### 规则 5

- 只有验证成功的支线成果才 merge / cherry-pick 回 A 线

## 12. 你以后只要记住这一句

> 主线负责规划、派生、收口；支线负责实验、记录、提交；GitHub 负责同步代码和关键文档；成功成果最后再回主线。
