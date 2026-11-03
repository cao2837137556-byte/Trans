# 超算硬盘故障后的本地实验结果保存核查

2026-10-02。用户转述学校超算硬盘损坏；故障磁盘、路径覆盖范围及可恢复性尚未确认。本次仅读取和校验本地文件，不连接远端，不重跑诊断、推理、训练或原始解码。

## 核查结果

近期主线的结果证据已在本地保存。核查范围为 runs/legacy_*delivery* 下26个现存归档（包括代码包及历史草稿），全部SHA256与原侧车相符；5份已返回export_manifest共1662项文件的内容和大小匹配。其中Job176411三个文件未展开到evidence子目录，但在原回传归档内，已直接流式读取并验证SHA，不能将未展开误报为丢失。其余1659项在对应展开目录中核验。

这不是全部半年历史、全部原始数据和全部运行缓存的完整备份验收；本机D盘也不等于第二份独立介质备份。

最新Job177891的321375653字节回传归档SHA仍为35f371d04763e24d6a1ee4af0f3a9eff5e463c981da538ec84006e11051bb450，916项返回文件全部匹配。包括12个分类/参考头终点权重、源归一化器、源CAL分数与阈值、两个开发池逐行分数/决定、UID及标签元数据、完整报告、训练轮次记录、协议和运行日志。此前结果复算记录、G1–G4和D1诊断证据也在本地。原工程完成/科学FAIL结论保留。

较早的qref训练、设备确认、预检、UNSW资格/评价/恢复、缓存审计与v2失败证据回传归档均存在且外包哈希通过；本次未将所有旧归档的内部内容重新展开逐文件验收。范围和文件名见audit.json。

## 仍依赖远端的部分

Job177891的export_manifest明确省略了完整features及spool/snapshots.sqlite，理由为留远端复用；它们未包含在本次916项结果回传中。

- snapshots.sqlite：4477841408字节，约4.17GiB。
- LEARN/CIC_DEV/UNSW_DEV完整特征及参考特征：大型运行缓存留远端。
- 分片特征、tensor校验证明等其他运行缓存也有远端保留条目；详情见原export_manifest的omitted。

未远程核查，不能断言这些文件已经损坏或无法恢复，也不能声称它们已完整保存在本地。若学校不能恢复这些父缓存，现有QUERY_TAIL v1包无法按既定缓存复用路径直接运行。先核查远端恢复及完整原始输入可用性，再提出版本化缓存重建/算力迁移计划和资源预算；不自动重新训练Job177891，也不以其他旧特征替代固定父缓存。

QUERY_TAIL设计、实现、127034字节交付包、19项直接交付文件seal及本地验证记录都已保存且哈希通过。现有记录中真实P/T/K尚未启动，没有该新方案的真实实验结果可丢失。

## 证据与下一步

核查记录：runs/local_result_preservation_audit_20261002/{audit.py,audit.json,audit.json.sha256}。

建议将项目代码、runs/mainline_docs及各正式delivery/pullback目录再备份到另一块物理磁盘或可靠备份存储，保留归档与SHA侧车。当前只完成本地保存状态核查，没有创建异地/独立介质备份。

solved: 已确认近期主线结果回传和最新模型终点在本地、内容未损坏。
changed_mainline: no scientific change; parent-cache availability now uncertain。
active_blocker: 超算故障范围/恢复情况及父features/SQLite可用性未知。
next_action: 等学校说明实际受损路径；恢复后只读核验固定父缓存，再决定恢复既定链或另立重建方案。


补充核查：E3所用冻结netFound-base编码器checkpoint在本地supercompute_transfer/issue27ckda_d0_representation_compatibility_20260811_r2/payload/vendor/netFound-base/model.safetensors，698780900字节，SHA256 e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105，与父runtime_contract一致。前端模型权重没有被本次远端独有缓存范围覆盖。spool另有target_provenance.jsonl.gz未回传，不能忽略。用户要求重要结果必须保存本地，已写入mainline_workflow_and_hpc_continuity_20260909.md。
