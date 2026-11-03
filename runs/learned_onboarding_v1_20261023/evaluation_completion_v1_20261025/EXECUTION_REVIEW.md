# 2026-10-25 V4-EVAL1 正式启动验收

用户已明确授权“本次实验就在这个服务器运行完成吧。开始”。本次已在现有云服务器单次启动独立评价，启动验收通过，已进入真实评价；尚未完成全部矩阵，也不代表科学指标通过。

## 当前执行与证据

- 北京时间 **11:12:03.760** 启动，root `/srv/paper04/learned_onboarding_eval_20261025_v1`，unit `paper04-learned-onboarding-eval-20261025-v1`，MainPID `5174`，InvocationID `2fb248ddc3ce43b19900483b1ba7d4ae`。
- **11:13:25.838** 写入 `SOURCE_REUSE_VERIFIED.json` PASS：源绑定、原 FIT/CAL 运行时、科研代码及目标 manifest 身份一致；新增训练更新为0，未重新校准。**11:13:25.840** worker 进入 `evaluation`。
- **11:14:40** 远端核查为 active/running、NRestarts=0，外层状态持续更新，EXCEPTION_STOP 和 child_exception 均无，stderr 为空。RSS峰值 **4,215,074,816 bytes，约3.926 GiB**，低于8 GiB守卫；这是启动阶段观测，不代替后续峰值。新增评价输出已写11,863 bytes，尚无 CHAIN_COMPLETE。
- **11:15:01** 现有进度页 HTTP200、connected=true，版本、root、启动时间、PID、InvocationID及真实evaluation阶段均匹配；原V4异常历史保留。原页面任务由 Windows Task Scheduler 托管，pythonw、无定时触发器、无限运行时长、零服务重试；普通程序每60秒读取，SSH隐藏窗口，无持续AI轮询。

原始证据见 [启动回执](EXECUTION_RECEIPT.json)、[启动验收](STARTUP_ACCEPTANCE.json)、[页面验收](PAGE_ACCEPTANCE.json)、[本地托管验收](PAGE_TASK_VERIFIED.json) 及 `operations/STARTUP_SNAPSHOT_20261025_111442.json`。

## 执行范围与资源

复用原V4已封存的FIT、CAL及相关输入，完整执行 **40个主比较＋12个控制比较**，不从原49份摘要自动续跑，不重新训练或调整阈值、λ、分母和科学规则。原V4继续保留 `EXCEPTION_STOP`，不会补写其 CHAIN_COMPLETE；新执行完成只证明本次独立评价及复用阶段组合完成。

原956件输入清单固定，systemd将 `/srv/paper04` 设为只读，仅新root可写。已验CPU quota8核、数值4线程、单重worker、8 GiB进程树RSS守卫、16 GiB systemd硬限、swap=0、Restart=no。科学FAIL继续完整配对；身份、数据、数值或资源异常停止并保留现场，零自动重试。

新评价results单独守 **2 GiB**。经验上界估计为 **2,018,840,552 bytes**，距上限约122.68 MiB；这是预算估计，不能保证完成。原V4的2,149,196,167 bytes作为只读输入单独记账，不声称原整链2 GiB合同通过。物理盘余量充足；新旧现场及备份保留。

## 验证、备份及待完成事项

独立执行器16项工程测试在本地及实际云Python3.9全部通过，覆盖输入保护、资源预算、异常终态与最终矩阵验收；均为合成验证，无真实拟合或目标查询。进度页38项无网络测试通过。部署清单SHA256为 `3dbdc6482da8aa54dedfd557c607b20604da6c29428b377d1eb91f739aef95e1`。

重要模型、CAL及小证据已独立下载，归档与所有成员SHA均通过。本地归档 `parent_backup/sealed_models_and_calibration.tar.gz` 为 **53,279,763 bytes**，SHA256 `3176bdd08bc58dfd14750751c287aa5ba60bea179a3f35899879be7408a6b95c`。备份范围是关键模型与校准证据，尚非完整FIT和逐条预测备份，见 [备份清单](parent_backup/BACKUP_MANIFEST.json)。

最终仍需：完整52格、paired内嵌与叶子摘要一致、原49份摘要全部相等、52份gzip完整CRC及行数、评价seal和原输入最终SHA验收。CRC/行数不冒称逐行UID/trace独立回放。科学收益须等完整结果分析，启动验收不替代科学PASS。

预计启动后约1.5—2小时完成，属于基于历史运行的粗估，以实际进度为准。后续由普通后台程序继续，用户通过 [现有进度页](http://127.0.0.1:18765/) 查看；本次不提交超算、不停机或清理现场，也不建立AI轮询任务。
