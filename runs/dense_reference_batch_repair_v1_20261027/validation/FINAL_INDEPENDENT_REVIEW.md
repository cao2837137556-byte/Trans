# 新批次修复 overlay 独立复审

结论：当前代码与执行说明的独立复审 PASS，未发现阻止封包的具体问题。本回执仅确认本地工程准备；最终 overlay 封条、分发包及独立解包验收尚由主手完成，不代表已获准或已执行云端作业。

## 已审范围

- `run_repaired_chain.py`、`repair_gate.py`、`run_repair.slurm`、`inert_test_support.py` 及三份 `test_*.py`。
- `encoder_adapter.py`、`build_encoder_budget.py` 与预算；成功克隆回执及晚期门禁失败覆盖旧 COMPLETE 的处理。
- `README.md`、`EXECUTION_CARD.md`、`REPAIR_MANIFEST.json`、false `APPROVAL_TEMPLATE.json`。
- 冻结的 source-CAL、IndexedMatrix、supervisor、原 chain 和实际源侧数据绑定。

## 工程检查

1. 默认链路入口只做封条与预算重算，未进入真实执行分支前不导入模型／Torch、不加载 checkpoint、不前向；执行必须额外使用新 scope-bound 批准，固定三阶段 `runtime → encode → source_cal`。
2. 原 r2 的 1,492 文件、编码器、CAL、supervisor 和原始门禁继续受原封条约束。新 overlay 与输出独立；没有修改旧 r2 或旧 launch／diagnostic overlay 的代码路径。
3. 仅 logical B1 的已打包张量复制为 16 行，逐行 tensor 哈希及输出字节一致后返回一行。B2–B16 原样传递。原104完整零容差比较、原数据集顺序、UID queue 与原 bank merge 保留。
4. 编码后新增 receipt 必须通过预算、实际计数、UID、ledger、原104零误差检查后才允许 CAL。最终 adapter 检查失败会把此前 frozen COMPLETE 改为 EXCEPTION_STOP，禁止进入 CAL。
5. 预算文件原始 SHA 与 canonical 内容 SHA 已明确区分，adapter 与新链使用相同约定，不会把含末尾 LF 的文件摘要与内容摘要直接混比。
6. HPC 测试根由 `PAPER04_FROZEN_R2_TEST_ROOT` 显式绑定；本地可选干净 extracted r2。没有固定 Windows 解包路径作为 HPC 必需条件。Slurm 脚本独立通过 `bash -n`。
7. 新链的 SIGTERM handler 会抛出异常并经过原 supervisor 的 finally／kill_tree；启动器对链 PID 发 TERM 后等待其退出，保留外层失败回执。此项为静态控制流核查，没有在 Linux 上对真实科学进程做终止实验。
8. 启动器仅使用 amd、4 CPU、16 GiB、12 小时、CPU-only、四线程、no-requeue。进程树 RSS、磁盘、输出和阶段／总时间限制继续交给冻结 supervisor；没有自动重投或数值容差放宽。

## 本地验证证据

- 独立运行新链 `test_repaired_chain.py`：9/9 PASS。覆盖实际冻结 chain 的 inert 三阶段衔接、未验证编码阻止 CAL、错误命令与 matrix 阻止执行、零容差、ledger、运行时漂移、false 批准及资源／范围约束。
- 审核 adapter 验证回执：17/17 PASS，含 3 个独立 inert child 集成。真实冻结 encoder.main、原104比较及原 bank merge 被执行，但运行时和 forward 均为替身；另验证克隆不一致和晚期 UID receipt 错误不能留下成功结果。
- 实际源侧只读数据核查：LEARN 766,727 行；CAL 148,819 行，正常 33,147、攻击 115,672。所有 fit_role 与 CAL 索引逐行一致，保存 trace 的 UID 顺序一致。E3 源数组为 float32 `[766727,794]`，q14 为 float32 `[766727,14]`。4,728 密参考均合法，与 CAL 的组件交集为 0。没有运行 CAL 计算或模型。
- 预算文件 SHA256：`8a9216bb0aa64c3e2be0f097796c245475d76aa0dc50e226bedcb681838e9944`。
- 真实旧运行时原始 receipt SHA256：`b404d8c8db68495846dabfbc540a3ff325157b145876240396e0ecd7c939173d`。
- 已审最终 adapter SHA256：`cf0bca425f8e49ab9465ca6865a3e074f9e081202fd2c78042c1b1ec8fe789d5`。

## 范围、预算与仍待验证

执行卡、manifest、模板与预算一致：21,764 逻辑行（原104 + 21,660新参考）、22,514物理位置、750额外克隆、50个单例批次、1,501个逻辑批次。SOURCE_REFS 最终为 4,728 个唯一 UID；副本不进入参考库。模板为 `user_authorized=false`，不复用已完成的136位置诊断批准。

179591 的8个锚点结果支持批次大小数值路径问题，但正式修复后的原104门禁仍未通过真实运行验证。本次复审、合成测试及预算重算均没有真实模型前向、checkpoint加载、训练、生产补编码、CAL、目标评价或远端提交。5–8小时只是执行卡中的规划区间，未当作实测HPC ETA。

完整目标矩阵仍缺冻结第三池 BASE/B2 资产；该 prefix 不可顺带变为目标 A/B 评价，也不产生新的目标误报率／检出率。后续须在最终封包验收后获得新的云端执行授权。

## 最终分发包独立核验补充

此节更新前文的封包待项：最终 r1 分发包独立核验 PASS。没有重复执行测试，也没有真实前向、模型操作或远端操作。

- 15 个 sealed 文件逐个重算 SHA 均一致；`OVERLAY_SHA256SUMS` 原始字节 SHA 为 `ff81556b59801426c10779908be2363f002f8945673c0eac9fa235bc9cc1d57a`。
- 分发 archive 实测 30,454 字节，SHA 为 `279d5006cc7f155f22186e6d5d2b09c0926fb26e2085a99798649f037ee087a7`。
- 直接审查 archive：恰好包含 15 文件及封条，共16个 regular-file 成员；路径集合准确，无 symlink／hardlink 成员，每个成员内容 SHA 均匹配封条。已解包目录也恰有相同16文件，逐成员 SHA 与封条字节完全吻合。
- `validation/final_r1/ACCEPTANCE.json` 原始 SHA 为 `96f2b68f049e406eb6e0c4ca06c401d64598fc06d1d4fa5ef208ffb06b50a734`。本地与解包两份测试日志及两份 dry-run 日志、bash 检查日志的 stdout／stderr SHA 均独立核对，全部匹配该回执。
- 两份测试日志均为26项、OK；两份 dry-run 均为 DRY_RUN_PASS、0真实前向、0 checkpoint加载、0远端提交、0目标评价，且绑定相同15件封条和21,764逻辑／22,514物理预算。这里只复核日志和身份，没有重跑26+26测试。
- 本轮另核对原 r2、旧 launch overlay、source8 diagnostic 三份旧封条的原始 SHA 与条目数，分别为1,492／5／9且与验收回执一致；全部旧成员未变的全量校验见验收回执，本轮不重复逐成员扫描旧包。
- false 批准模板保持 false。该分发包的工程验收现已完成；云端运行仍待新的明确授权，修复后的原104真实门禁仍为 `PENDING_NEW_AUTHORIZED_JOB`，目标矩阵仍未就绪。
