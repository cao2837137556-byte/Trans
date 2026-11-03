# CICIoMT2024：Benign 资料门与原包保留建议

2026-11-02，America/Los_Angeles。状态：`BENIGN_METADATA_INSUFFICIENT_NO_NEW_RAW_DOWNLOAD_NO_DELETION`。用户同意继续核查，并询问若数据不能使用是否需要删除。本轮落实目录/响应元数据检查与指定范围存储盘点，未把询问解读为删除指令。

## 本轮继续核查结果

已登记目录此前及本轮可见 `Benign_test.pcap` 的正式下载链接，已保存完整目录清单也含 `Benign_train.pcap`。可见条目没有字节数、采集日期、设备身份或构建来源。针对这两个已知地址各做一次独立 HTTP HEAD，均403且没有可用的文件长度、Content-Disposition、Last-Modified或Accept-Ranges；HEAD未下载PCAP正文。独立HTTP并不继承用户浏览器登记会话，不能仅据此认定文件本身不可下载。

当前应用内浏览器进一步导航 train 目录后，页面明确显示 `Registration required. Please go back and register.`，没有新提交个人信息或获取登记凭据。此前 test 页面可见条目是已有页面状态，不能把它当作新请求仍有登记权限的证明。

作者预印本的有界HTTP请求403，浏览器公开页面只显示受Akamai保护的中间页面，未取得可核实的新增正文。没有绕过保护、提取会话或继续猜测路径。

因此 Benign 两文件的实际大小、真实日期、同目标身份、可信正常依据及完整7200秒上下文仍未知。**未增加原包下载；资料门在缺乏资源/内容边界时收束，不宣称Benign资格失败，也不淘汰整个数据集。** 继续条件仍是先获得可核验的官方文件大小/捕获与构建说明，或合法有界的原包获取范围；完整方法角色/ACK与UDP证据通过前不运行模型。

机器回执：`runs/ciciomt_raw_qualification_v1_20261102/BENIGN_METADATA_GATE/` 中的 HEAD_RECEIPT、PREPRINT_HTTP_RECEIPT、UI_OBSERVATIONS 与 BENIGN_GATE_STATUS。此前四包资格失败及独立讨论封存材料保持不变。

## 是否需要删除

**最终确认主验证和补充用途都不需要时，可以删除原包，不需要为负面资格结果永久占用本地空间。** 应保留来源URL、字节/帧数、SHA256、时序/身份/方向核验与资格失败回执；这些小文件能证明当时为何未采用，但不替代原包的完整重放能力。

当前指定范围共6份PCAP、2,656,576,686字节，约2.474GiB：

|材料|占用|当前建议|
|---|---:|---|
|D盘受控Idle/Active两正常包|0.447GiB|保留，仍有正常侧补充潜力|
|C盘Downloads同两正常副本|0.447GiB|优先重复清理候选；真删前重核D盘保留副本当前哈希，仅释放C盘空间|
|D盘两攻击原包|1.580GiB|指定范围各仅一份；先保留，救援/补充用途最终放弃后列归档或删除候选|

旧验收回执证明正常副本建立时内容相同，本轮只盘点实际stat大小并核验小回执哈希，没有把旧哈希描述成新的全量副本校验。若日后删除副本，必须先确认保留件仍完整。若选择转存超算个人存储，需实际核实额度并完成上传、哈希及可取回核验后再处理本地；本轮没有连接超算或上传。

详细清单与保留建议：

- [存储盘点](../../ciciomt_raw_qualification_v1_20261102/RETENTION_REVIEW/INVENTORY.json)，SHA256 `1e1322f568c72606f2a1ff831eeef6981c8a88cb8d761945e0dd3da303ae674c`。
- [原包保留建议](../../ciciomt_raw_qualification_v1_20261102/RETENTION_REVIEW/README.md)，SHA256 `012d21a0ef344a937b916c9c960edaf7e0d16fd52934048648d429df5cdd72fd`。

本轮没有删除、移动或复制PCAP，未扩大数据下载，0模型/编码/距离/训练/云端作业。C5 p=3与A/B冻结保持；没有后台下载、作业或持续AI监测。
