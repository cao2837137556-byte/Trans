# V3 正式启动验收

用户于本轮明确授权“修复好了，就可以启动实验了。”。已于北京时间 **2026-10-24 13:26:46** 在原空闲实例启动独立 V3 全链；不是验证服务，也不是恢复或覆盖 V2 输出。原 V1/V2 现场、权重、错误与旧回执全部保留。

## 部署与数值身份

- 远端根：`/srv/paper04/learned_onboarding_20261024_v3`。
- 服务：`paper04-learned-onboarding-20261024-v3`；InvocationID：`39b19278c6384b5cbc75361d45643287`。
- 包含 697 件文件；10 个源文件与已云端源侧验收的 V3 一致，原 30 件冻结交付未变。原始模型、训练配方、输入角色、分组、seed、终点及科学判据不变；新 float32 推理后端身份明确单独记录。
- ZIP SHA256：`e57171182d5be9ef0580bf4fb08ee87624fc05a0d4a8cf886f0f48a49d3e43c9`。
- 部署清单 SHA256：`6cf9383a3250fd9b6908749708419883e901abadc0df4b27d7f61883d614e755`。
- 实现清单 SHA256：`7875f1e7a2dcd97e3a2f6838d2757442393a4bac8d10314280711ef854954ccf`。
- 源传输 16 件、43,458,560 bytes，单独存放在 V3 `inputs/source_head_archive`；传输阶段真实目标查询读取 0。

本地独立审查逐件核对 ZIP/清单/大小、源文件身份、配置、新路径和完整启动命令；无阻塞项。V3 新增数值测试已纳入普通 unittest discovery，原 49＋新增 5＝54 项，adapter 4 项单独计数。

## 13:28:17 启动验收快照

证据为 `operations/STARTUP_ACCEPTANCE_SNAPSHOT.json`，结论为 `EXECUTION_RECEIPT.json`：

- systemd `active/running`，无 `EXCEPTION_STOP` 或当前 stage 异常。
- 实际 Python 3.9.24／Torch 2.5.1+cpu 下，54 项测试全部通过，无失败、错误或跳过；adapter 另 4 项通过，真实目标读取 0。
- 数值后端为 `learned-onboarding-rowwise-float32-v3-20261024`，与已验收版本一致。
- `tests` 和 `prepare` 已完成，当前 `validate`。该快照尚未进入真实辅助头/修正器训练；不把全链已启动说成训练已完成。
- 当前 cgroup 内存 3,990,597,632 bytes，进程树 RSS 峰值 4,136,660,992 bytes，低于 8 GiB RSS 守卫。
- 已验 CPU quota 8 核、数值 4 线程、16 GiB cgroup 硬限、swap 0、单重 worker、`Restart=no`、`KillMode=control-group`。

固定链由普通程序继续：tests→prepare→validate→preflight→fit→calibration→target→evaluation。fit 按登记执行两个辅助头和三个修正器；正式 QUERY_TAIL seed27 复用，不重新提取前端。源核验与资源 preflight 通过后才进入训练，CAL 封存后才装配目标评价。科学 FAIL 继续登记配对；身份/数据/数值/资源异常停止留现场，零自动重试。

## 页面与后续边界

原进度页 `http://127.0.0.1:18765/` 已切到 V3，当前用户的既有任务计划服务继续独立托管；页面进程由 14752 切换为 56024，父进程为服务宿主，HTTP /status 已收到启动时间之后的新 V3 状态且 connected=true。见 `operations/PROGRESS_PAGE_RECEIPT.json`。后台普通程序读小状态，不持续调用 AI。

此后不为等待训练而继续 AI 轮询。后续阶段、H 与困难信号、三个修正器、CAL λ、A/B 科学结果仍待程序执行，不能用启动 PASS 推断科研收益。
