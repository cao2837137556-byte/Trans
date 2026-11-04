# Edge worker v3：进度 I/O 优化封存包

结果：将已验证的独立进度I/O候选集成为新worker；本地93项检查和60000条选中查询元数据核验通过。完整Linux工程门与小anti独立复核仍待完成，未提交新作业。
影响：v1/v2、181645运行现场与失败证据保留；逐包顺序、数值状态、样本seal、C5、模型、阈值、统计口径不变。仅两条实时进度路径取消强制持久化，保留原子替换。
下一步：小anti按REVIEW_REQUEST.md复核；在新运行预算落实后进行同运行时真实小切片与完整工程验收，再决定正式评价。源码/交付包封存不等于执行卡已获授权。

## v2停止的实际结果

181645于1小时57分37秒停止，根因`EDGE_REPLAY_DEADLINE`，为原预算收尾预留；整树采样峰值3551694848字节，约3.31GiB，scratch清理成功。最后心跳为UDP 1523712/3215732帧，非精确最终处理帧。没有完成工程门，没有正式外部检测成绩。

停止后只读校验确认：NORMAL完整24124条（含4124参考），HTTP完整20000条；chunk、索引、每条序列化快照SHA、完整UID覆盖、v2绑定和EOF覆盖均通过。UDP仅71个部分chunk，没有角色COMPLETE，不能作为模型输入或中间帧恢复点。完整产物保留在超算，未复制大数组到Git。

## 代码变更范围

- `worker.py`增加helper导入，并在原replay.install作用域外包一层`install_progress_io`。
- `progress_io.py`与独立候选字节相同，仅路由当前output的`PROGRESS.json`和`replay_status/REPLAY_HEARTBEAT.json`，JSON字节和原子替换保持一致；文件/目录fsync从这两处移除。
- `checkpoint.py`、`streaming.py`、`evaluate.py`、`reporting.py`、`engineering_gate.py`、`runtime_control.py`、`budget.py`与v2字节相同。全部repo/ood冻结代码未改。STOP/PASS权威回执、CURRENT、完整角色标记、批次和资源守卫保持原持久化规则。
- 测试新增8项进度路由检查与3项集成/版本隔离检查；旧测试桩补齐`_write_json`接口。首轮93项中的1项测试桩错误保留于`validation_history/initial_full_run`，生产实现未因该错误降级。
- 生成/交付脚本更新版本、待复核状态、helper与父版本字节比较依赖闭包。旧review仅为历史证据，不声明小anti已经通过v3。

## 恢复边界

默认使用全新v3输出目录，按原顺序从原包起点重放。v3的完整依赖绑定变化，**不自动采用v2 spool**；已经完整的NORMAL/HTTP可作为后续兼容迁移的依据，但迁移证明尚未建立。不能删改旧BINDING或简单改SHA来使其通过。

相同v3身份、运行时、seal和输入下，原完整角色/批次恢复机制仍有效；UDP中间帧恢复仍不支持。不得以放宽依赖检查换取“续跑”。用户已允许后续恢复或全量重放，本封存版实现后者，不暗中缩减数据范围。

## 封存与验收

`LOCAL_ACCEPTANCE.json`记录本地验收与明确待办；`DELIVERY_DELTA_MANIFEST.json`记录增量tar SHA和所有成员。原863件基包、该增量及已存在原PCAP构成交付闭包；原包、模型、tar和大census JSON不进Git，保留校验清单/压缩元数据。

执行卡仍为DRAFT，`execution_ready=false`、`independent_review.status=PENDING`、Linux恢复PENDING；工程预算1CPU/8GiB/7200秒仅为草案，181645的一次授权不自动复制成新作业。正式评价未获授权。

本地命令依次为`python -B run_local_checks.py`、`python -B verify_reporting_metadata.py`、`python -B build_cards.py`、`python -B prepare_delta.py`。所有测试只使用本地合成/元数据；旧181418小切片及单文件Linux写入对照不替代v3真实全链路验收。
