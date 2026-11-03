# 正常／攻击参考竞争v1：源侧提交与启动回执

**最终更新：180228已正常完成，COMPLETED / 0:0，结束记录2026-10-30 10:23:15北京时间；科学 SOURCE_SIGNAL_FAIL / SAFETY_FAIL，A/B未启动。** 六模块24,000更新全部完成，23分28秒、峰值7.09 GiB，预算内、无异常或自动重跑。候选撤回原RAW TP超过累计保护限额。[完成核验与监控显示修复](20261030_reference_attack_competition_completion_and_monitor_repair_codex.md)已记录证据与限制；18783已明确显示完成时间和失败原因。下文为10:00启动历史快照。

2026-10-30北京时间。**源作业180228已经提交，并在node185／amd实际运行。当前科学结果未知，尚未进入主阶段或A/B。**

本回执替代“等待SSH恢复／尚未提交”的当前状态。用户先前“把实验运行上超算吧”的授权及本次“已连接，能看到远端Linux提示符”已落实为一次源执行，不重复索取许可，不把此前断连算成科学作业失败或重试。

## 提交前已通过

- 封存设计SHA：`47847119e5cae15ca41cf7433b615cf5741dac9d1ef59f70077090f88444c5c7`。
- 部署zip SHA：`fe7fa08de72329b8ed8b7607a27795bc5f4c6a22ba46e6a90903573139e409ab`；只补104个缺失文件，没有覆盖历史文件。
- 远端合并178个文件身份核验通过，含69项代码／metadata依赖及63个真实源输入，约2.626GB，errors为空。
- 源运行环境实际核验为Linux／Python3.11.11／NumPy1.26.4／Torch2.5.1；没有另装Python3.9或修改共享环境。
- 超算原环境99项合成测试全部通过，unittest计时17.350秒；测试没有启动本轮真实训练或A/B。
- 源提交器在sbatch前创建独占持久锁，仅执行一次固定Slurm脚本，`--no-requeue`，返回码0、明确job_id=180228。没有自动重提。

对应本地原始回执位于`runs/reference_attack_competition_deployment_20261029/runtime/`：`REMOTE_SOURCE_INPUT_ACCEPTANCE.json`、`REMOTE_ENVIRONMENT_ACCEPTANCE.json`、`REMOTE_SYNTHETIC_ACCEPTANCE.json`、`REMOTE_SOURCE_SUBMISSION.json`。

## 已确认的实际启动

提交锁时间UTC 01:59:39（北京时间09:59:39），明确提交回执于01:59:42保存。首次工作快照UTC02:00:15（北京时间10:00:15）显示：

| 项目 | 实际记录 |
| --- | --- |
| Slurm | 180228／RUNNING／node185／amd |
| 源工作进程 | PID1271488，RUNNING |
| 当前阶段 | SOURCE_INPUT_IDENTITY，源输入核验 |
| 计时／峰值RSS | 26.852秒／2,178,826,240 bytes（启动快照） |
| 真实训练更新／距离对／头评分 | 当时均0，后续随进度变化 |
| 主阶段job | 尚无 |

这只证明作业和科学worker实际启动，不代表六模块已训练、源保护门通过或误报率下降。启动快照保存在`runs/reference_attack_competition_progress_20261029/runtime/FIRST_JOB_SNAPSHOT.json`。

## 预算与后继

源两方向×Q/N/C共6个小模块，每模块4,000步；4CPU／0GPU／8GiB／4小时／2e9距离对／2GiB输出与临时文件／24,000更新上限保持。出现技术异常或资源超限即停止、保留现场，没有自动重跑或改配方续跑。

只有新候选源完整PASS及封存、累计攻击保护和收益／对照门通过，才考虑独立主C模块；主CAL真实RAW逐字节重放、D0历史锚、零撤回保护及λ>0通过后，才做一次A/B。本次提交器不自动投递target。主阶段仍沿用已有超算Python3.11加NumPy2.0.1私有overlay，实际新前向兼容性由主CAL核验。

## Codex右侧进度

[新进度页](http://127.0.0.1:18783/)已经接通；已请求在本聊天右侧面板显示，不启动外部浏览器。普通隐藏collector每5秒只读同步18785，工作心跳、调度、科学判定各自显示；超过90秒未见工作心跳则未知，不以网页刷新冒充worker仍在运行。当前模块训练条为step/4000，不作为全程百分比。旧18775／180007终态不变。

本地collector PID34396、页面服务PID32968，端口18783；当前VSCode SOCKS端口64785只用于已有SSH通道，口令不进入报告或投递包。无需AI持续轮询。既有179700正式开发成绩仍为A FPR3.993482%／召回100%，B FPR9.519654%／召回99.966594%；本轮尚无新A/B结果。
