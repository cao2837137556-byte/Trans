# 真实特征准备中止：F4 前缀哈希格式修复

2026-09-10。用户授权一次真实特征准备，准备通过后直接进行固定双臂训练及终点检查；
异常停止、零重试。准备实际失败，条件未满足，训练没有启动。

## 真实尝试与确定原因

目录 `runs/frontend_paired_train_preparation_v1_20260910/`，状态
`INPUT_OR_EXECUTION_STOP`，CLOSED。监督 SHA256SUMS：
`c6a866db132e7ec1d78eae130e9b16b3007a526576f25a8ac8cc8df32d955c00`。
耗时 4.625 秒，聚合内存峰值上界 360,812,544 字节，worker_count=1、restarts=0。
worker 以 0 退出只表示失败 receipt 已写出，不能解释为准备成功。

traceback 定位到 prepare_data 的首个 PREFIX_IDENTITY 检查。既有两份源特征
的完整 SHA 已先验证通过；源码流程和冻结 plan 显示随后读取首个 parent 上下文
90,128 字节（172×131×4，source_offset=0），finite/长度检查通过，在首个目标
前缀身份比对失败。新 features.f32le 大小为 0，尚未写入任何合格上下文。
真实训练、模型前向、旧教师前向和优化器更新均未发生，没有原始包重读。

旧 F4 的 prefix_bytes 明确定义哈希输入为：

```
b"F4_INPUT_V1\0" + struct.pack("<II", prefix_events, 131) + prefix_float32_le_bytes
```

新 V1 准备代码只计算最后的裸特征字节 SHA，遗漏了 12 字节版本标记和 8 字节
形状信息。因此它与继承 receipt 使用了不同的哈希输入，必然不一致。这是新实现
的兼容错误，不能用来断言特征损坏、前端无效或学习方案失败。
旧 F4 源码 SHA `9c729a3165d19042549723f029235734595131d5e7ba344a3f605cca89677200`
和旧 N1 feature_contexts 的相同封装为直接依据；没有重跑历史实验。

## 修复与验证

V1 实现包与真实失败目录保持不变。新增 V2 support/runner/controller 命名空间、
启动/状态脚本，以及纯函数 prefix_digest。唯一输入校验变化是恢复上述原有
F4 字节封装；目标名单、特征源身份/偏移、输入数值、模型、初始化、loss、seed、
训练顺序、更新数、资源限制与判定门槛不变。V2 plan、bound_recipe 和 initial
文件直接复制 V1 字节，并校验一致；不重新选择初始化。

新增 8 项兼容测试，直接 AST 投影固定旧源码中的 prefix_bytes，只对生成数组
执行该函数；包括全部 1–256 个前缀、固定小端头部布局、裸字节错误复现、
前缀/后缀变更、范围拒绝、非连续输入和使用旧函数生成 receipt 的准备集成。
另在 V2 重跑原 47 项模型/调度/准备/判定测试及 10 项标准库监测器测试，
共 **65/65**，两个 V2 脚本解析 **2/2**。新增头部布局 fixture 初次把标记长度
误写为 11，改为真实的 12 字节后通过；初次日志保留，不改旧真实证据。

原合成测试使用新代码同样的裸字节假设，验证了内部一致性却漏掉历史格式兼容。
本次直接以固定旧函数作独立参考补齐这一缺口；不能把合成通过当作真实准备
或模型能力已通过，也不能保证后续不会出现其他实际异常。

修复证据：`runs/frontend_paired_train_prefix_fix_v2_20260910/`。
修复实现包：`runs/frontend_paired_train_implementation_v2_20260910/`。
只读就绪和完整性结果见修复证据中的 final_verification.json。

## 下一步与时间

本次准备授权已消耗，未自动重试；真实训练授权原本以准备成功为条件，尚未执行。
下一次若获明确授权，可执行一次 V2 真实准备，通过后直接进行原配方双臂训练和
终点检查，无需准备成功后再问一次；失败停止，不重试。
准备上限仍 1,800 秒/8 GiB/256 MiB；训练检查上限仍 14,400 秒/8 GiB/512 MiB。
这是停止上限，不是结果到达时间预测。当前还没有真实训练速度，无法可靠预估
结果时刻；开训后用实际每轮速度更新预估。没有计划中的新增科学方案阶段。

V2 命令入口（未运行）：

```powershell
.\scripts\start_frontend_paired_train_local_v2.ps1 -Stage prepare -AuthorizeFeaturePreparation
.\scripts\show_frontend_paired_train_status_v2.ps1 -Stage prepare
```

训练使用相同脚本的 `-Stage train -AuthorizePairedTraining`。V2 准备与训练
目录均未创建；禁止重启 V1，禁止因此改规则、重放流量、HPC、K 或设备实验。
