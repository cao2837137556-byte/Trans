# V4 已封存模型的独立评价收尾

用户2026-10-25明确授权“本次实验就在这个服务器运行完成吧。开始”。本目录实现并部署评价专用执行器；原V4的训练、校准和失败现场保持原身份，不从头重跑。

- 新root：`/srv/paper04/learned_onboarding_eval_20261025_v1`
- 新unit：`paper04-learned-onboarding-eval-20261025-v1`
- 原只读输入root：`/srv/paper04/learned_onboarding_20261024_v4`
- 实际环境：原`/opt/paper04-venv/bin/python`，Python3.9.24 / Torch2.5.1+cpu / NumPy2.0.1，CPU四线程。

## 修复范围与资源合同

旧输出预估漏计了评价产物，原整链于2GiB守卫停止。原失败链继续保留 `EXCEPTION_STOP`，不改写其2GiB合同、停止回执或输出。

新执行是**使用既有封存数据的独立完整评价**：新写入的 `results/evaluation` 继续严格守2GiB，原V4的2,149,196,167 bytes作为只读输入单独记账。新旧现场合计物理占用显式计入磁盘余量；这不是把原全链的输出压回2GiB或声称其资源合同曾通过。备份输入权重的运输归档另有256MiB上限，不是新增科学结果。

按原逐池最大单元压缩大小×26×2，另加control_plan×2、52份摘要×2、40份内嵌摘要×2及16MiB杂项，完整新评价上界估计为 **2,018,840,552 bytes（约1.880 GiB）**。这是经验保守估计，实际2GiB硬守卫不变。原预检内存估计7,700,771,456 bytes继续作为预算，低于8GiB RSS守卫；外层监控进程树，systemd另设16GiB硬限、swap=0、CPU quota8核、数值四线程、单重worker、Restart=no。

systemd将`/srv/paper04`设为只读，只允许新root写入。没有新检测头/修正器训练、重校准、目标调参、额外seed、自动重试或从49格自动续跑。新目录完整执行40主格+12控制格，保证冻结比较矩阵。

## 身份与完成验收

`parent_inventory.json`封存956件原部署/结果/目标输入文件的SHA、大小及mtime，执行前后全核、运行中定期核stat和目录成员。原代码路径、`common.ROOT`、20件实现SHA、FIT/CAL/preflight seals、源装配、原cut、阈值/λ和完整运行时必须匹配。只调用原冻结 `pipeline.evaluate_targets`；不通过会写旧输出的原service入口。

最终要求完整40主格+12控制格、paired内嵌摘要与叶子文件一致、原49份摘要全部原样复现、52份gzip到EOF的CRC/行数核验、评价seal及原输入最终SHA核验。CRC/行数检查不冒称逐行UID/trace独立重放。科学FAIL仍完成全矩阵，工程完成不等于科学PASS。

新root的`state/CHAIN_COMPLETE.json`只证明本次独立评价完成，并指向原封存源阶段；不会给原V4补写CHAIN_COMPLETE。异常写明确终态，保留最后内部快照，但阶段worker不再以RUNNING冒充终态。

## 必要验证与操作

新执行器16项工程测试在本地及实际云Python3.9通过，测试只用合成数据，无真实拟合/目标查询读取。进度页另38项无网络测试通过，显示V4-EVAL1与复用阶段、独立2GiB预算、原V4失败历史；SSH/SCP隐藏窗口，进度只由普通程序每60秒读取。

`operate.py`提供显式prepare/inspect/build/upload-test/backup/launch/status动作，没有自动循环或实验重试。正式动作按本次回执，不照抄历史命令重复启动。`operations/`保留原始调用回执，`EXECUTION_RECEIPT.json`记录真实启动；用户通过[现有进度页](http://127.0.0.1:18765/)查看，AI不持续轮询。
