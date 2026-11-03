# 持续输入修复 v2：实现与验证

2026-09-28。用户授权按 Claude 回复的四项共识作版本化修订并实现 v2，附 D1 核对。**实现及本地工程验证完成，待 Claude 复审改动范围；真实 P/T/K 未启动。** v1 仍保留且禁止上传。

## 交付身份

- 修订文档：`legacy_continuous_input_core_repair_design_v2_20260928.md` 及 SHA256 侧车。
- 新合同：`runs/legacy_continuous_input_core_repair_design_v2_20260928/design_contract.json`。
- 新合同 SHA256：`8396629e6e2495d98bfc1d4a5288f0570bc1a95d653596419005eb96470f55bd`。
- 新包：`runs/legacy_continuous_input_repair_delivery_v2_20260928/legacy_continuous_input_repair_v2_20260928.tar.gz`，342,818 字节，43 个本地模块。
- 包 SHA256：`7087d73186693ad4c8482027b82ce2f4b6027ed5c1c290045b44a8f0ddef2768`。
- 包不包含原始数据和模型权重；操作预案见交付目录 `OPERATE_HPC.md`，不是本轮启动指令。

## 修改与依据

`continuous_input_v2.py` 用 namespace 纳秒单调性替代全 capture 时间断言；永久 poison 独立于空闲重置和物理 GC。完整头的 payload 截断包进上下文但不能做查询；缺头包不产生 token/state，并将后续历史标记不可信。只有相邻合法作用域事件严格 >60 秒的完整空闲重置可清除此标记，B1 poison 永不解除。地址/端口缺失则直接停，避免零端口默认值掩盖受影响连接。

新增 `continuous_audit_v2.py`，同帧调用原 ScopedPrefixes/BoundedNetfoundPrefix，比较异常身份、原查询资格与固定目标身份。新增纳秒倒退、旧新分类不一致、固定目标受到异常或缺头历史影响都会保存可定位证据并停止。四个已知异常捕获单独优先核验，随后保持原排序重建，先行/主重建异常与目标摘要必须完全相同。真实的 B2 分类和旧回执对账仍 NOT_RUN。

`continuous_model_v2.py` 将 Bank 元数据检查抽为共享函数；`continuous_data_v2.py` 在原始文件扫描/解码前调用全部 Bank 时间/完整性及错误 donor 检查。神经网络、损失、优化器、split、seed、参数和样本不变。源数据实际选中 217 个捕获，外部 2 个；catalogue 总数 302 不等于本次执行数。静态回执含所有选中捕获的源 SHA、包数和三类旧异常计数，并固定来源文件 pins。

`continuous_evaluate_v2.py` 的主攻击判据读取合同指定 weighted_rate；历史 CIC Q 回归差额继续按 rate。正常误报和逐 UID 零新增漏检条件保持原意。每设备/速率组保留 positive/rows（攻击即 TP/总数）与两种召回，CIC 缺速率项标为 NOT_AVAILABLE。zero-vector 报告分阶段调用行增量及累计调用行数，不冒充独立样本数。

早期诊断固定为 Motion/Samsung 各前 6 个攻击 UID，P 保存完整当前包证明，K 输出各臂分数/判定、通用阈值、参考资格和撤警。没有专用阈值或新训练。导出包含先行预检、全捕获异常流、早期 12 条证明和汇总；全量大型缓存仍保留超算并列入省略清单。

本地封装复核额外发现 Windows 默认文本编码可能把旧 PowerShell 模板的 UTF-8 BOM 解码为普通字符，导致参数声明失效而普通语法解析仍可通过。v2 生成器已显式使用 utf-8-sig，实际 transfer_v2.ps1 已修正，并验证真实 ParamBlock/Mode 参数和语法。没有修改旧脚本或调用上传。

## D1 结论

只读取历史封存 Q 决策/概率、原阈值及 DEV 元数据，没有运行模型。原文件封存、全部 UID 顺序、manifest SHA、权重层级及 79045/79056 均核对一致。

| CIC DEV | 加权攻击召回 | 未加权 TP/总数 |
|---|---:|---:|
| Q ensemble | **99.938458%** | 79045/79056 |
| Q seed 27 | 99.944053% | 79046/79056 |
| Q seed 127 | 99.942579% | 79045/79056 |
| Q seed 227 | 99.949648% | 79047/79056 |

ensemble 的 Eufy/HeimVision 加权召回分别为 100%/99.876916%。历史基线达到加权 99%，不存在本次口径切换造成的旧基线门槛冲突；不保证 v2 成功。结果文件和可复算脚本位于 v2 设计目录 `D1_weighted_feasibility.json`、`check_d1.py`。

## 验证证据与限制

干净解包后 **52/52 合成测试通过**：原 36 项回归加 16 项修订测试。新增覆盖永久 poison、跨键倒退、payload 截断、缺头污染超过 72 包仍阻断、严格空闲重置边界、缺失 namespace、float 舍入隐藏的纳秒倒退、固定目标命中、同计数不同身份拒绝、四捕获顺序、独立手算 TCP/UDP tokens、加权与未加权反例、合同门槛读取、阶段 zero 增量及提前 Bank 时间核验。

Windows 和本机 WSL Linux 各 **6/6 安装器/失败导出测试通过**；Linux 模拟 sbatch 验证明确参数、唯一提交、重复阻断、调度拒绝及状态不明后保留占位，无真实调度调用。4 个 Bash 文件语法、PowerShell Mode 参数、Python 3.9 AST、干净解包及源码/包 pins 通过。

工程中间日志保留：新增指标反例的首次夹具漏写 session_id，补齐后通过；首次 WSL 内联命令遇到跨 shell 引号问题，改为已保存的本地脚本完成检查。以上均为合成/本地交付验证，不是实验重试。最终证据以交付目录 clean_synthetic.log、installer_tests.log、linux_delivery.log、linux_submit_mock.log 和 acceptance.json 为准。

没有真实解码、真实 E3 前向、优化器/CAL 更新、外部评分、下载、上传、HPC 提交，也未打开新保留池。目标机器真实 E3 数值/资源预检必须在之后获授权的作业内执行。额外四次解码纳入原预算；12 小时储备不代表运行时间保证。独立 ID NOT_RUN，CIC/UNSW 都是 consumed DEV，论文暂停。

最终核对 HEAD/分支、8 个无关修改、v1 源码/合同/包与论文快照不变。最新导航指向本报告和 Claude 复审回复，不改历史记录。
