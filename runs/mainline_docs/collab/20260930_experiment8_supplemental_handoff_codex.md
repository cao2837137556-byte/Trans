# 给实验8的补充交接：实施入口与容易漏掉的边界

本记录由上一对话于 2026-09-30 补写。用户已在实验8安排阅读近期文件；不必重读半年历史。本记录不是新执行授权，也不覆盖实验8后来已经收到的用户授权、已完成工作或新证据。原对话从此不再并行修改生产代码、提交任务或推进实验；只留下此补充文件，避免共享目录冲突。

## 1. 交接时真正完成到了哪里

- 主线是 `QUERY_TAIL` 学习修复 v1，设计完成，生产实现、模型合成测试、新真实 P/T/K 都还没有在本对话启动。当前验收 `DESIGN_READY_FOR_IMPLEMENTATION` 是设计验收，不能当工程或科学 PASS。
- 入口：`runs/mainline_docs/legacy_query_tail_learning_design_v1_20260930.md`。
- 必须同时读 `runs/legacy_query_tail_learning_design_v1_20260930/` 下的 `design_contract.json`、`implementation_and_review.md`、`research_notes.md`、`design_acceptance.json`。只读通俗正文容易漏掉 loss 估计、并列处理与数据权限。
- contract SHA256：`8fc236975039773580fef8d40705d205dc382dbc5159c43833928958c62a6ecd`。
- 正文 SHA256：`c478767227348668bcf738f32fcee2e3f51d1527eb77fd452bcc05fd6a3cf892`。
- 这是 Codex 自审方案，没有 Claude 对本版的审查。用户说 Claude 没 token，不表示需要再找他批准。

## 2. 已经查清的，不要重新绕一圈

Job177891 的当前包/连续输入问题已修复并完成训练；它是工程成功、联合科学门槛失败。RECENT 在 UNSW 的实际源阈值下攻击召回 99.9849%、正常误报 21.2832%。96.6038% 是用 DEV 标签事后寻找每设备 1%FPR 阈值得到的诊断上界，不是实际部署结果；每设备放宽到 2% 的上界仍只有97.5301%。单靠设备标量阈值的路线已被否定，不重复 D3。

G1–G4 及正常包头补查已完成。完整证据在 `legacy_continuous_input_job177891_overlap_diagnosis_20260930.md` 和同名 run。UNSW 此池的攻击查询全为入站 TCP SYN&&!ACK；只有5个长攻击 component，不是很多零散小攻击。83.57%的加权损失在标注开始60秒以后；冷启动不能解释全部错误，但实际窗口信息不足 H2 尚未完全排除。

正常剩余误报90.38%加权质量来自当前包 ACK／data；不代表整个窗口均为该阶段，也不支持“SYN必报、ACK放行”。H1 新正常覆盖不足、H3 阶段监督失配仍是假设。三 seed 共同错误也不是任何未来模型的能力上限。

## 3. 源训练权重是本轮新增的重要事实

`source_inventory.json` 已按实际 FIT 分层重新算权重。Hydra仅471行，却占攻击类权重25%；TCP活动429350行占41.6667%；UDP占33.3333%。ACTIVE_UNANNOTATED正常131823行仅占正常类权重17.9479%，其余2670行占82.0521%。这是既有分层规则，不凭这些数字认定规则错误。

因此本版没有 SYN 专项重加权。先前“载荷攻击原始行至少80.54%”不是加权训练压力。**精确源 SYN 正/负权重与真实保留窗口描述仍待远端 snapshot**，合并到实现包的 P 中，不再另开无边界诊断。

## 4. 实现最容易踩的坑

- 单个 `782→128→1` 头：原768维 RECENT/E3 + 当前包14维。q字段从准确的 query_frame 定位，不能假定当前包在数组最后；方向沿用窗口首个IP源。不能由16位长度 token 猜 payload 长度。
- E3、source normalizer、原训练权重、全部 FIT 行、原评估分母保持；新增 q 不拟合目标域，不输入地址/端口/设备/标签/绝对时间。
- `fit_cal_identity` 从父协议保留了 `eligible_rows` 等历史参考学习字段；本轮全部分类头必须使用 **FIT617908/CAL148819**，不能误用历史 reference-eligible 子集567175/136962。以本版明确总数、完整 UID 和目标说明为准。
- tail按**全部源 FIT 正常的最高1%加权质量**取，不是1%条数或batch最高几个；并列分数块按原权重比例分配边界剩余质量。每轮刷新，轮内固定，是pAUC启发的滞后近似，没有原论文SOPA的收敛保证。
- pair负例也必须重新前向并反传，不能只保存旧logit；正例用2×原BCE权重，不在batch内重新归一化；最后一个batch的系数用实际b。
- R0直接复用177891 RECENT；新增QUERY_BCE、RECENT_TAIL、主候选QUERY_TAIL各3seed，共9个头/869040更新。都从匹配的未训练初始化开始，不是把旧终点追加40轮。不能看结果再自动换主候选。
- 本轮不使用目标reference，也不是入网机制完整实验。原入网增益/否决零新增漏检标NOT_TESTED；ID_NOT_RUN、holdout关闭。共同攻击/FPR门槛继续保留，另加原攻击活动/协议保护检查。

## 5. 数据在哪，怎样节省超算时间

本地验证结果根：
`runs/legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891/runs/real_repair/`

远端原 run：
`/public/home/jiangxinwei.zr/work/legacy_continuous_input_repair_v3_20260929/runs/real_repair/`

本地有元数据、DEV逐行分数/决定、source CAL logits、normalizer、原head；**完整新特征和约4.17GiB snapshots.sqlite仍在远端**。不要把缺失本地文件说成输入坏了，也别拿旧 early-prefix 特征替代。

spool SHA：`591890270a6c6d0c29d796cc765a870f943bc3a2c810f09f86f8fabec8271c3a`。
features/SHA256SUMS 的绑定 SHA：`259ef4eadac38a4be0a30d79bd55b4513cf01a96a90ee9577a3a51c28100b040`。
完整其他 pins 在contract/P_COMPLETE。先验证清单与实际数组，再复用。q全三池1094929行约58.5MiB，原E3特征全三池约3.13GiB，可mmap。无需重新下载、解码PCAP、重跑E3、启16个feature worker。

用户工作方式：助手实现/验收/打包，用户上传、在已认证超算终端提交和拉回；给明确区分本地PowerShell与远端Bash的指令。不要拿历史SSH凭据尝试无人值守登录。Python3.9必须实际验证；资源申请和程序资源guard同步冻结。状态输出要有阶段、进度、失败原因、终点与拉回入口，不要靠模型持续轮询烧token。失败保留证据、零自动重试。

## 6. 工作区与权限

交接再次只读核对：分支`codex/exp-mainline`，HEAD`4b28747b09480471e2bac1beb3a9badf27280efb`。不切分支、不reset、不新worktree、不清理大量有意保留的untracked产物。

8项无关tracked修改位于`runs/issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12/`；已验证hash见新设计run的`workspace_verification.json`。两个mainline导航文档本来就有大量历史修改，不把整段git diff当成本轮新增。此交接只新建本文件及侧车，不再改共享导航，以免和实验8争用。

本对话最后授权/完成的是设计与必要已消费数据分析。实验8若已有新的实现或完整链执行授权，应沿用，不重复索要；若没有，不能将本记录当成新训练/超算授权。一次明确完整链授权即可覆盖最终包P/T/K，不人为拆成每阶段再问。

用户目标是低OOD误报与高攻击检出同时成立，跨设备/环境但攻击机制相近是主要泛化范围，不要求凭空解决全新攻击机制。原数据攻击能力必须保护。新数据已经参与设计，修好可算开发进展，独立迁移确认仍需之后未参与设计的设备/环境。论文暂缓，先把核心能力做稳。

## 7. 下一步

依据已交付设计实现、合成语义验证、资源静态审查和版本化整链包；把源阶段统计放进P。禁止重跑已完成G1–G4，禁止未经证据自动换前端/加模块/调门槛。方案有真正语义问题应指出并版本化修订，不能因为前任写了方案就放弃独立判断。
