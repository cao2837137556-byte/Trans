# 受约束新设备入网 v1：代码实现与合成验证

2026-10-15。用户已授权代码实现。本轮完成正常参考准备、双视角支持与受约束修正、源侧定参、QUERY_TAIL 接入和配对评价。真实实验尚未开始；本目录不提供新的召回率/FPR 结论，也不是独立超算提交包。

最终 **89 项合成测试全部通过**，结果见 [implementation_receipt.json](implementation_receipt.json)，逐项测试见 [synthetic_tests.log](synthetic_tests.log)，新代码指纹见 [source_manifest.json](source_manifest.json)。四组测试均使用生成数据、合成模型或 mock，不加载真实 PCAP、前端 checkpoint 或检测头。验证脚本同时核对原 QUERY_TAIL v2r1 压缩包、合同和入网 protocol 的固定 SHA256，全部未变。

## 已实现的部分

| 代码（项目根目录下） | 作用 |
|---|---|
| `repo/ood/constrained_onboarding_reference_v1.py` | B0/B1/B2 完整候选普查、组件与协议预算、参考 q14、原始解码与固定 E3 编码入口；保留 CPU/解码器/输入身份 |
| `repo/ood/constrained_onboarding_core_v1.py` | 同设备同协议、两个不同组件、严格时间/帧资格；双视角联合支持；源 FIT 半径和 logit 尺度；源 CAL 逐 seed/集成/合法库保护及 lambda 选择 |
| `repo/ood/constrained_onboarding_query_tail_adapter_v1.py` | 校验父缓存、已完成 R3 和原阈值；逐位回放 CAL/CIC/UNSW 已存分数与判断；仅用冻结头额外计算 FIT 定参分数 |
| `repo/ood/constrained_onboarding_runner_v1.py` | 源参数封存后执行同头单独/加模块配对；原库与新库身份、逐 UID 轨迹、等价库复用、独立的错误设备参考对照和失败停止回执 |
| `repo/ood/constrained_onboarding_evaluate_v1.py` | 原完整 UID/权重分母、设备/协议等分层、误报与攻击 TP 参考资格份额、逐 seed/集成零新增漏检、完整系统门槛 |

对应 `test_constrained_onboarding_*_v1.py` 四个文件覆盖上述边界。新增的跨模块测试把生成数据的参考准备、编码、带哈希加载和配对评价串通；目标标签改变不会改变源侧定参，等价参考库仍单独运行各策略的控制计划。测试验证加权指标与既有官方评价器一致，新增漏检不能用救回其他攻击抵消。

无参考、非法参考或无支持时分数精确回退；不得使用未来、其他设备或查询自身补主参考库。修正幅度有上限，源侧选择零新增漏检的 lambda；这不是对目标攻击安全性的保证，真实目标仍须逐 UID 验收。完整系统缺少三设备回归或必要攻击证据时保留 PENDING，不把流程 COMPLETE 写成科学 PASS。

## 接口与后续执行顺序

1. 缓存恢复后核验完整 Job177891 当前输入目录，以及封存 QUERY_TAIL v2r1 的真实完整运行。只有精简 pullback 不够：旧导出省略的 q/window、完整参考快照与前端缓存仍需恢复。缺失会报 PREPARATION_REQUIRED，不会自动重跑或换旧前缀缓存。
2. 先接 `QUERY_TAIL`（R3）与 `OLD_BANK`，同一个头、阈值、seed、UID 与评价权重比较 H_ONLY 和 H_PLUS_M。当前入口还支持原封存 QUERY_BCE/RECENT_TAIL 臂，不新增训练。
3. 新统一参考需依次 `raw` 准备和 `encode`，然后由 `--banks-manifest` 接入 B0/B1/B2。配置示例见 [configuration_examples.md](configuration_examples.md)，只说明接口，不代表真实材料/运行已就绪。
4. 真实三设备回归仍按已有重放协议另行补齐；当前生产 adapter 只加载两个已登记开发池。完整系统会持续 PENDING，直到经过验证的第三池及必要证据接入。
5. MLP/QUERY_BCE、TabM、LightGBM 的新比较实现是后续工作。共用模块 API 已准备好，生产接入仍需各自经过验证的结果适配器。便携 bundle 的通用 CLI 仅允许合成验证，不能靠 JSON 自称已验证而进入生产。

真实入口形式（参数须由恢复后核验的实际路径填写，此处未运行）：

```text
python repo/ood/constrained_onboarding_query_tail_adapter_v1.py --parent <完整runs/real_repair> --head-run <完整runs/query_tail> --design runs/legacy_query_tail_learning_design_v2_20261010/design_contract.json --protocol runs/onboarding_materials_and_protocol_20261015/protocol.json --arm QUERY_TAIL --output <新的输出目录>
```

输出包括 source calibration、输入/库身份、scores、decisions、逐 UID 支持与修正轨迹、全分母/较晚子集报告、分层覆盖、错误参考控制、各池门槛和整体科学判定。B0/B1 等实际参考完全一致时记录 `equivalence.json`，明确不是独立证据。没有事前按元数据冻结的匹配供体计划时，错误参考对照记录 NOT_AVAILABLE，不根据目标分数临时挑供体。

参考 raw 入口默认内存限制不超过 150 GiB，记录进度和资源信息；没有测量真实全流程峰值或耗时，不能据合成测试承诺实际资源需求。没有加入自动重试、超算提交脚本或改变既有任务资源。

## 复验

在已具备依赖的项目环境运行以下命令，只运行新合成测试及代码/合同身份检查：

```text
python runs/constrained_onboarding_implementation_v1_20261015/verify_implementation.py
```

本机使用 Python 3.9.13、NumPy 2.0.2、PyTorch 2.8.0+cpu。真实编码另需已有封存前端运行包（含 vendor、checkpoint 和依赖）与 tshark，未下载或安装这些资产。

固定方法来自 [原配置](../onboarding_materials_and_protocol_20261015/protocol.json)。其中 NOT_IMPLEMENTED 字样是制定配置时的历史状态，不原地改动冻结文件；当前实现状态以本目录回执及 [主线交接](../mainline_docs/mainline_handoff.md) 为准。选型后的正常功能覆盖、外部攻击多样性、独立确认及论文证据待办继续保留在主线顶部。
