# Frontend-F0 ZT-2 真实两遍解码实现报告（2026-08-31）

状态：`IMPLEMENTED_AND_PREFLIGHTED`。本文只报告实现与执行前门，不报告任何科学结果。

## 1. 授权与边界

项目所有者已明确授权 ZT-2 的实现与真实执行。授权范围严格限定为：

- 本地打开 Step-0b 已审定的 30 个 fit/select packet member；
- 对冻结的 25,467 个 target cutoff 做确定性、零训练、因果两遍解码；
- 只产出语义可编码性、上下文层级和计数型结果；
- 禁止训练、学习参数、模型/representation/score、report/FINAL、网络与 HPC。

## 2. 实现身份

- 语义引擎：`repo/ood/issue27frontend_f0_zero_training_semantics_v1.py`
  - SHA-256：`00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa`
- 真实执行器：`repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py`
  - SHA-256：`ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60`
- 真实执行合同测试：`repo/ood/issue27frontend_f0_zero_training_semantics_real_contract_tests_v1.py`
  - SHA-256：`22afc0a01f02cccdd9f6ba1ea10527b93a7f5fa6be42e4317601dd06b1a1ab89`
- FROZEN 合同：`runs/mainline_docs/frontend_f0_controlled_zero_training_semantics_protocol_frozen_20260831.md`
  - SHA-256：`532bb52e4d03c0321f1e874cc4bd7a49fca3391943c0dd23a1968fd69ac3c0ee`

钉死输入：target metadata `d6fbba24...c36d`、旧 availability `b1b4f2fd...b6099`、30-member identity attachment `5deddd66...849c`、R0 identity audit `41b52491...8e11`。执行器在任何 packet member 打开前逐项重算身份并检查 2 GiB 最小剩余空间。

## 3. 实现形状

执行器复用 Step-0b 已验证的两遍、成员级流式解码纪律：

1. 第一遍只发现冻结 target cutoff 所需的事件/上下文生命周期；
2. 第二遍按原始包序重放，在 exact cutoff 生成一行语义状态；
3. 每成员精确守恒后才原子写 checkpoint；
4. 30 成员、25,467 UID 全部守恒后，才打开旧 `missing` 位和角色/设备/族描述列作纯描述 join；
5. 不请求 payload，不读取标签构造语义，不加载任何学习模型或 embedding 坐标。

TShark schema 只含帧序号/时间/封装/长度、二层与三层端点、协议号、TCP/UDP/SCTP 端口审计字段、ICMP 类型码和 GRE key。SCTP 端口不进入上下文键，按 FROZEN C1 归入 H2。

## 4. 执行前验证

- Python 3.9 语义引擎合同测试：`36/36 PASS`；
- Python 3.9 真实执行器合同测试：`20/20 PASS`；
- 两个实现文件均通过 Python 3.9 `py_compile`；
- `git diff --check` PASS；
- preflight：25,467 target、30 member、TShark/R0/合同/输入身份全部 PASS；
- 单真实成员 pilot：1,100 packets、600/600 targets，H1/H2/H3 均实走，末态 active context 为 0。

首次合同测试失败来自测试装载器未在 `exec_module` 前注册动态模块，触发 Python 3.9 `dataclass` 装载要求；已仅修复测试基础设施并复跑通过，科学实现未因该失败改变。

## 5. 下一步

在本提交推送后，以钉死执行器从零运行 30-member ZT-2。最终判决只允许：

- `ZT_SEMANTIC_COVERAGE_PASS`；或
- FROZEN 中具名的 count-only NO-GO/工程失败状态。

无论 PASS 与否，结果都不等于检测性能提升，也不授权 CE、学习型挑战者、训练或 FINAL。
