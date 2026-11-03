# V4 正式执行与启动验收

用户本轮明确授权“可以动手运行。”，独立 V4 全链已于北京时间 **2026-10-24 19:08:45** 启动。原 V1/V2/V3 的失败现场保留，本次不恢复或覆盖其输出。

## 正式身份

- root：`/srv/paper04/learned_onboarding_20261024_v4`
- unit：`paper04-learned-onboarding-20261024-v4`
- InvocationID：`226cc64bb84747518f72afe05abe1969`
- 包含 701 件 payload，ZIP 共 702 个唯一成员；清单、逐件 SHA／大小、完整闭包在本地及云端核验。
- ZIP SHA256：`6158ed45c31c9be87bbbd8513b49b1f4768207662e81863d9308702fd9a00a45`
- DEPLOYMENT_MANIFEST SHA256：`86df420f38e128afaa027b7d0a650d3b5c8ba1e981123164cd42fc4ed95ce363`
- implementation manifest SHA256：`47c5b456f056fed50bd999bc72807b47ff33cec7017489c2baab424eacbbbc51`
- 完整规模内存证明 SHA256：`e91a49c04ecee2685face9bbf85d1d0ce93e234a216da6d51a87748c043bf6ec`，纳入部署清单，12 个科研源文件与已验修复候选逐件一致。

配置 archive、state、results、source_assets、target_bundle 全部使用独立 V4。正式头、源缓存和已登记输入身份保持；16 件源资产按 allowlist 在 V4 新目录组装并验证，组装阶段目标查询读取 0。实际源证明通过新目录下的输入／运行时身份门。

首次本地封包发现诊断 manifest 仅包含 Python 闭包，未复制非 Python 配置，构建在任何远端操作前停止。该部分目录保留为上层 `packaging_attempt_20261024_missing_asset_closure`。最终 builder 补齐 implementation 全 artifacts 和有父清单 SHA 的 source_members／remote_config，再构建并验证正式 701 件闭包；没有为此修改科研源码。详见 `PEER_REVIEW.json`。

## 19:11:12 启动验收快照

`operations/STARTUP_ACCEPTANCE_SNAPSHOT.json` 与 `EXECUTION_RECEIPT.json` 记录：

- systemd active/running，MainPID 非 0，NRestarts=0；外层 RUNNING，无外层或阶段异常。
- 新部署实际 Python 3.9 环境中 63 项 unittest 全部通过，无失败／错误／跳过；adapter 另 4 项通过，fixture 真实目标读取 0。
- tests、prepare、validate、preflight 完成；已进入 **fit**。该快照未观察 optimizer 更新数，不据阶段名虚报训练步数或模型完成。
- 正式 preflight **READY**，完整规模内存证明 **VERIFIED** 且 SHA 匹配。估计峰值 7,700,771,456 bytes（约 7.172 GiB），原 8 GiB RSS 门保持。
- 外层进程树 RSS 已记录峰值 4,957,700,096 bytes（约 4.617 GiB）；这是启动阶段快照，不能代替后续训练峰值。
- 已验 16 GiB cgroup 硬限、swap=0、8 CPU quota、数值 4 线程、单重 worker、Restart=no、KillMode=control-group；fit 10 小时、chain 24 小时、2 GiB results／2 GiB target staging 的原守卫不变。

普通程序按冻结顺序继续：tests → prepare → validate → preflight → fit → calibration → target → evaluation。fit 包括两个辅助头和三个修正器，正式 QUERY_TAIL seed27 复用；CAL 封存后才装配目标评价。科学 FAIL 完成登记配对；身份／数据／数值／资源异常停止留现场，不自动重跑。

## 页面与后续

已有 `http://127.0.0.1:18765/` 页面已成套切换 V4 状态／worker／unit／标题，显示 V4 启动时间和身份，V3 仅在历史区。页面由原 Windows 任务计划 `Paper04-Progress-18765` 托管，新页面 PID 60516；`operations/PROGRESS_PAGE_RECEIPT.json` 证明已收到对应 InvocationID 的新读取。31 项无网络状态测试与 JS 语法检查通过，保留无窗口 SSH/SCP 和每 60 秒普通程序读取。

启动验收已完成，不持续调用 AI 轮询。三模块训练结果、CAL λ、A/B 效果及完整终态均待后续程序执行；没有用启动成功推断科研收益。上层 `REPAIR_RECEIPT.json` 是本次授权前的修复验收历史，以本目录正式执行回执作为最新启动事实。
