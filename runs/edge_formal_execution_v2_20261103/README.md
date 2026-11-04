# Edge worker v2：实验11复核修复

结果：修复实验11复核提出的R1–R4；本地回归与封存身份核验见LOCAL_ACCEPTANCE.json。
影响：v1源码、执行卡、失败/复核证据保留。C5、阈值、样本seal、参考与统计口径未改。
下一步：在取得具体运行授权后，用同一冻结Linux运行时完成有界工程验证；当前未提交作业、未评价外部效果。

## 四项修复

| 复核项 | v2行为 |
| --- | --- |
| R1 依赖身份不完整 | 入口验证原863件基包清单、全repo/ood、hnr和v2 Python目录清单，以及卡内所有附加依赖；完整依赖进入snapshot绑定；即使所有spool已完成也先验证依赖。 |
| R2 父子RSS漏计 | 最外层监督进程轮询自身和全部后代；恢复子进程运行时保留的主进程内存计入合计。最终资源记录来自监督进程。 |
| R3 旧PASS遮蔽新失败 | 整轮使用唯一attempt_id和卡SHA；OS文件锁阻止同目录并发写。子进程只写候选结果，监督进程在检查和清理后发布终态。缺卡、草案拒绝、准备失败均会使当前轮次为STOP。 |
| R4 主进程超时漏清理 | 监督进程预登记main/crash/resume三个精确scratch目录及所有权。Linux专属进程组终止、等待退出后才按清单清理；不能确认退出则保留scratch并明确STOP。持久spool不删除。 |

## 读取当前状态

`CURRENT_ENGINEERING_ATTEMPT.json`是唯一权威入口，指向`engineering_attempts/<id>/RUNNING|PASS|STOP.json`并绑定SHA。使用`runtime_control.current_status(output, attempt_id=..., card_sha256=...)`核验指针、回执和PASS候选文件；不要搜索历史目录内任意PASS来判断当前状态。

根目录`ENGINEERING_GATE_RECEIPT.json`、`PROGRESS.json`仅为兼容镜像/进度。它们都带attempt_id和卡SHA；写入先于CURRENT的原子提交，因此异常中断时以CURRENT为准。子进程`CANDIDATE.json`本身不是已验收PASS。成功终态的`resources`才是整树资源证据，候选中的主进程局部观测不替代它。

RSS名义轮询间隔0.25秒，回执记录实测最大间隔与峰值时各进程RSS；磁盘按60秒及最终检查采样。均非瞬时严格峰值，站点/cgroup硬限制仍须由未来作业配置落实。监督进程本身遭SIGKILL、机器掉电不可能执行Python清理；此时CURRENT停留RUNNING，不能宣布PASS，可按保存的精确所有权清单核查。

## 检查点兼容性

v2采用`EDGE_SCIENTIFIC_INPUT_BINDING_V2`，保守绑定完整依赖。旧v1 spool缺乏这些身份依据，不自动升级或复用。应给v2新的输出目录；v1产物保留。v2工程卡与正式卡使用相同科学输入绑定，未来仅在代码/原数据/运行时/选择seal完全一致时复用已完成角色。编码和评价仍绑定具体执行卡；不完整角色仍不可用于推理。

## 验证与交付

在本目录运行：

```text
python -B run_local_checks.py
python -B verify_reporting_metadata.py
python -B build_cards.py
python -B prepare_delta.py
```

`build_cards.py`要求测试覆盖的源码SHA与当前目录完全一致。卡保持草案，既不产生用户授权，也不调用模型或提交作业。独立复核字段说明本次由用户指定的实验11 Codex跨聊天复核v1并修复/自验；它不声称小anti已复核v2，下一次独立复核由小anti负责。

交付闭包是原863件基包加新增量；增量覆盖卡上全部非基包依赖，包括此前未随基包交付的小型历史证据。大模型和原PCAP不重复打包；数组及tar不进入Git，仅保留SHA清单。目标端先验证完整依赖，随后才能打开spool或调用模型。

预算仍为拟议1CPU、8GiB、7200秒，scratch预留32GiB、scratch/output各24GiB采样守卫，无自动延期或重投。181418仅证明旧小切片；v2真实Linux冻结encoder恢复、末段UDP资源与完整批吞吐仍待执行。MEASURED_BUDGET、UDP_PROBE与census为v1既有证据的逐字节副本，不表示本轮重跑了原始包或模型。

开发验证历史：首轮完整回归79项中78项通过，1项测试诊断文件与内存终止发生竞态；已改为使用监督进程亲自采集的RSS数据，原FAIL回执保存在validation_history/first_full_run。另补充未确认进程退出、缺卡重入与候选篡改的回归；最终结果以新验收回执为准。
