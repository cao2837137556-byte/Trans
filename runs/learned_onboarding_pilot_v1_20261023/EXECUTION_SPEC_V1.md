# 学习式新设备入网：冻结执行规格 V1

日期：2026-10-23。状态：**DESIGN_FROZEN / NOT_IMPLEMENTED**。

本文是供后续 Sol 实现的研究规格，不是训练、远端连接、资源提交或修改现有作业的授权；本文自身仅提供设计规格。没有 H、学习器权重、新阈值、训练耗时或新效果结果。本文在方法顺序和数值配方上取代 PILOT_DESIGN.md 的待定段落；旧稿和审计保留历史，不改写旧回执。

## 1. 冻结问题与主线

同一基础头、同一合法参考库、同一完整查询池下，学习式有界减分能否减少正常误报，同时不增加该基础头原来已检出的攻击漏检？困难任务加权能否进一步优于同结构普通训练？前者是整体模块比较；后者才隔离困难任务的作用。

主线复用已验收 QUERY_TAIL **seed27单头**，不重训正式基础头、不按A/B排名挑头。新增两个辅助MLP和三个小修正器，共**5个训练终点**：AUX_G0、AUX_G1、L_STANDARD、L_HARD、L_QUERY_ONLY。所有新训练seed=27；无新ensemble。完整六设备源FIT可同时训练正式检测头与修正器，CAL仅最终校准，A/B仅评价。

辅助头用来真实模拟“当前头未拟合该设备”的入网任务，不是旧四设备主头/两外层设备先导。固定G0={Amcrest Camera, ArloQ Camera, Atomi Coffee Maker}；G1={Philips Hue Bridge, SimCam, Globe Lamp}。AUX_G0只在G0 FIT拟合，向G1 FIT提供折外分数；AUX_G1反之。两组各有结构可修正正常/攻击设备；不因新结果换组。两辅助头是本规格选定的困难任务实现，**不是所有学习式入网方法的一般前置条件，也不意味着正式全FIT头必须重训**。旧四设备/五终点外留先导不执行、不叠加。

QUERY_TAIL身份从既有验收清单解析到精确路径/hash，解析失败INPUT_NOT_READY，不换更有利头。以后改头沿用算法但重做该头任务、t/s、三个模块及CAL阈值/λ，不移植旧数值。已有九头及其v3配对保持原任务；本轮不读取它们进度。辅助MLP纯BCE与正式QUERY_TAIL训练目标不同，混合任务效果是待检验假设，不声称严格同分布。辅助头隔离仅限新头及其拟合预处理；冻结前端历史可能接触这些设备，不能称端到端完全未见或独立采集。

## 2. 已知事实与待装配项

- LEARN 766,727 行；固定 FIT 617,908、CAL 148,819。SOURCE_REFS 179 行，仅 LEARN 的104行可用于源任务；其余75条DEV记录不得混入。
- 源 E3 为已验收 LEARN.npy/SOURCE_REFS.npy 前768列；794总列中的其余26列不是q14。源 q14 已定位于已验收分片 `run/prepared/LEARN_q.npy`，尚未为本方案完成解包/ordered UID/数值绑定。参考 q14 须用既有已封存映射或 `reference.extract_old_bank_q14` 的原始槽位及 spool 身份路径获取，不能拼凑旧26列。
- 当前只有 timestamp 结构上界；frame、同捕获顺序、bank_end_frame 的完整因果尚未完成。六设备完整 FIT 最多4设备提供正常可修正任务、3设备提供攻击可修正任务。额外四开发设备子集只有 SimCam/ArloQ 两台的结论不可外推为全 FIT 只有两台。
- Atomi/Globe 单组件库不能用复制包、复制 UID 或重复组件凑两组件。Amcrest 的结构攻击可修正数为0；它的零新增不能算独立的学习式攻击保护证据。
- `NEW_RECONSTRUCTION_LINEAGE / PARENT_PARITY_UNAVAILABLE` 保持原声明；旧外层{Amcrest,Philips}对四开发设备划分已审计共享7捕获，此数字不属于新G0/G1三三划分。新G0/G1的capture/依赖交叉须在装配时另行统计；只承诺新头及拟合预处理的留设备，不称留采集/独立环境确认。A/B 已消费为开发材料，不用于拟合、阈值、seed或本配方选择；同头同库的开发环境改善仍是有效、有限范围的证据。

实现首先只装配源材料，seal后才可训练；全部权重及CAL选择seal后才加载A/B新评价查询。不能直接调用会提前回放目标的 `prepare_query_tail`/`prepare_modern` 作为训练准备入口，应拆出源专用只读适配，目标回放留到评价阶段。

## 2A. 两辅助头的冻结配方与真实隔离

每辅助头输入782维=[标准化E3的768维,q14的14维]，模型 `Linear(782,128)→ReLU→Linear(128,1)`，100353参数，复用 `query_tail_core_v2.classifier(27,782)` 初始化（E3基块按seed27初始化，q14输入权重初始为0）。不复用全FIT训练权重或全FIT E3 normalizer。对应训练组FIT全部正常/攻击训练，原 `legacy_qref_data_v1.weights` 的等类0.5、device/activity/capture/session层级权重，不加入参考、不筛H。

E3预处理在该训练组三设备FIT上按上述等类权重求每列加权mean及population std，float64聚合；std=0列scale=1并记录；无额外epsilon/clipping。q14为固定定义[0,1]不拟合缩放，若现成q14生成含任何数据拟合参数则必须证明参数不使用被留设备；否则不能称真实隔离，INPUT_NOT_READY。源参考不参与辅助头拟合或normalizer估计，被留设备参考仅作为随后入网任务输入。

AdamW(lr=0.0003,weight_decay=0.0001,betas=(0.9,0.999),eps=1e-8,foreach=false,amsgrad=false)。40 epochs、batch256、无early stopping/梯度截断/AMP；每epoch用torch CPU Generator(seed27)持续流randperm遍历训练组所有UID一次，含尾batch。BCE loss=`sum(BCE_i*w_i)*N/batch_n`，对应固定全局权重，不能batch内重归一。固定最后epoch40为终点；步数精确为40*ceil(N_G/256)，N_G由封存索引计算，不猜数值。CPU四线程，确定性算法；每头独立重置seed/Generator，串行训练。CAL/A/B、被留设备查询标签/统计/参考均不得进入该头optimizer或normalizer。

每辅助头完成后，在其训练FIT上产生t/s估计分数，在另一组FIT上产生折外任务分数；不拿另一组调头/early stop。对折外query使用该辅助头训练组FIT求得的t/s，关系E3也使用该辅助头训练组normalizer。标准化后的冻结E3仍继承旧前端历史；明确隔离层次。保存训练UID、预处理UID、留设备UID互斥证据及来源；预处理泄漏是异常，不用“仅校准”掩盖。

## 3. 数据与参考资格（所有臂共同）

接口沿用 `constrained-onboarding-bundle-v1` 的 rows/e3/q14/feature_uids/q_uids/logits；主线score为N维seed27；旧适配若返回N×3，验收其原列身份后只取27列，不把单列复制成三seed。辅助分数另存带head_id的N维数组。所有数组按显式ordered UID绑定，禁止仅凭行数或shape认为一致。源 FIT/CAL索引必须精确等于原封存索引；UID、组件及 `(source_sha256, session_id)` 交叉检查；源查询与任何源参考UID重叠一律异常停止。

参考资格沿用 `constrained_onboarding_core_v3.ReferenceBank` 的规则：同partition、自己的device、同protocol（6/17）；可信正常REFERENCE；完整设备库的reference_end严格小于query timestamp；同capture参考frame严格小于query frame；有bank_end_frame时query frame严格大于它；至少两个真实不同component。保留完整设备库截止，选子集/选两代表不能把截止提前。元数据缺失或矛盾是数据异常，不能伪装为“参考不足”。同组件较早历史可合法使用，不能无依据一律禁止。完整库bank_end_frame如上游不提供，必须证明现存合同允许缺省且逐参考frame仍核查，不能编造一个值。

新模块只共用这些时间/身份/组件资格；**不沿用v3的半径内正support门控**。它能学习半径外关系，是否有益由配对验证；因此不能声称仅替换v3的标量系数。无资格、空库、pre-bank查询精确复制原头分数/决定，不调用网络制造近似零。目标pre-bank历史重叠仅可通过既有 `causal_reference_overlap_v1.require_prebank_history` 白名单，仍保留且head-only；该例外绝不扩展至LEARN。

所有查询均保留在输出和完整分母。训练抽样省略零梯度回退行不等于评价删除它们；装配回执报告各类回退数、按设备/协议/标签的资格率、参考UID和真实组件数。错误参考仅限预登记诊断或源攻击保护，不混作正常查询的真实自身参考。

## 4. 固定50维输入、两组件关系与有界输出

E3先使用当前view对应头已绑定的768维normalizer（正式头用既有全FIT版本，辅助头用各自训练组版本），再L2单位化，严格复用 `_unit` 的零范数/非有限异常语义。q14原值在[0,1]，不拟合目标统计，不用CAL做输入归一化。

对每个合法query/bank：各参考计算 `dz=clip(1-z_query·z_ref,0,2)`、`dq=sqrt(mean((q_query-q_ref)^2))`。排序距离 `d=max(dz/2,dq)`；每组件选d最小代表，再取两个不同组件中d最小者。所有并列以reference UID字典序破除，次级组件ID仅作最终稳定顺序。此固定选择无可学习参数、无CAL半径。记有序代表r1/r2、`dqvec_k=q_query-q_rk`，完整合法组件数n。

每个基础头j分别产生50维float32输入，顺序固定：

| 槽位（0起） | 内容 |
| --- | --- |
| 0..13 | 当前query q14 |
| 14..27 | `(dqvec_1+dqvec_2)/2`，带符号 |
| 28..41 | `(abs(dqvec_1)+abs(dqvec_2))/2` |
| 42..45 | `dz1/2,dz2/2,dq1,dq2` |
| 46 | `clip((score_j-t_j)/s_j,-8,8)/8`，t/s只来自FIT |
| 47 | `min(log2(n)/6,1)`，仅输入计数截断，不截断真实审计计数 |
| 48..49 | protocol的one-hot，固定顺序6/17 |

输入不含device ID、label、UID、活动名、目标统计或CAL cutoff。网络为 `Linear(50,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→sigmoid`，共2177可训练参数；无dropout、batchnorm、embedding或注意力。三个臂相同初始化，PyTorch默认Linear初始化，seed=27，在相同软件/设备上保存初始权重hash。

每个任务只对应一个打分头，网络跨正式/辅助任务共享，输出a∈[0,1]；下标j表示任务的头身份而非ensemble列。固定最大修正预算c=0.25；训练修正 `score'_j=score_j-c*s_j*a_j`；部署 `score'_j=score_j-λ*s_j*a_j`，λ∈{0,0.05,0.1,0.25}。最终真实cut只用于CAL/评价，绝不输入网络；部署仅使用正式QUERY_TAIL seed27，不融合辅助头。s_j=0时该列精确回退，输入槽46置0且有明确degenerate_scale标记；全部s=0则导出no-op；若评价有合格FP则无收益FAIL，不除以epsilon伪造尺度。

不输出新增报警，所以攻击保护只可能维持或退化；已有攻击漏检保留。float64完成最终减分/比较，λ=0或不合格行用原数组拷贝保证bitwise；不得靠float近似保证边界。

## 5. FIT内分折、尺度和困难集合H

FIT查询以共享component_id或共享 `(source_sha256,session_id)` 的传递闭包组成不可拆group；按 `sha256('learned-onboarding-v1|'+组内最小UID)` 的完整整数模2分两折F0/F1。不按标签/效果重分，不把CAL补入。两折各须同时含正常/攻击且互补统计可计算，否则 `SOURCE_TASK_NOT_EVALUABLE`，不换盐重试。封存每UID→group→fold清单及计数。

正式头任务：对Ff查询，其t来自互补FIT正常分数的加权0.99分位数；s来自互补FIT正常/攻击等类权重分数的Q0.9-Q0.1。辅助头任务：t/s用其自己训练组三设备FIT计算，不用被留组，亦不再用F0/F1互补组混入被留设备。分位数严格使用v3 `weighted_quantile`（最低观察值达到累计权重）。类内统计用下述W，两类尺度各质量0.5。F0/F1仅隔离正式头难度/尺度标准的估计，不能撤销正式头看过源设备；辅助任务才是新头层的真实留设备分数。

最终部署正式头t/s按相同算法用完整FIT一次计算并seal。训练时每任务用对应头/分折t/s与normalizer，不混用尺度。禁止借用CAL cut筛H或输入损失。正式头已验收normalizer允许全FIT，不能挪用给辅助头。对每个源query固定构造两种view：正式头view、未拟合该设备的辅助view；两view都由该query合法自身/源donor参考条件计算，不增加独立query计数。

定义类内层级权重W：在给定类和当前样本子集中，依次device→activity→capture_id→session_id→component_id，每非空子分支等质量，叶内query UID等质量；每类归一为1。它比旧 `class_weights` 多component一层，须新命名，不能偷偷修改旧函数。标签只用于源训练/评价，不作推理输入。

所有合法自身参考的源正常query产生一个正常任务。所有源攻击query可对**所有**同协议、同LEARN角色且因果合法的源bank产生保护候选，含自己的bank；有任一合法候选则为攻击训练任务。正常始终用自身参考，攻击损失使用候选中的最坏情况，不把候选数量当独立样本数。资格统计分别报告自身和donor，不能用donor覆盖冒充自身可修正设备数。

H仅在上述任务集合内产生一次并seal。分别在正式/辅助view内，再对F0/F1、device、protocol、label分别进行加权排名（该组W重新归一）。正常难度为该view的 `(score-t)/s`；s=0记无可用难度。攻击难度为 `max_(合法bank) [(1-d2)*exp(-abs((score_j-t_j)/s_j))]`，d2为第二代表d∈[0,1]。它强调近边界且易被正常参考相似性误放的攻击；不称已观察到撤攻击，也不依赖学习器或CAL。选难度从高到低累计权重首次达到0.20的最短前缀，边界并列按UID；攻击bank并列按完整bank key。每个非空组至少1行，记录其真实质量而非声称恰好20%。不能根据A/B或第一臂效果重挖H。

每view内普通臂抽样分布P0=0.5W_normal+0.5W_attack。困难臂PH=0.25W_normal+0.25W_Hnormal+0.25W_attack+0.25W_Hattack；H内重新按同一层级规则归一。每view两类总质量各0.5；总抽样再固定正式view质量0.5、辅助view质量0.5。非H任务仍有质量，攻击保护三臂完全相同。L_QUERY_ONLY与L_HARD使用完全同一个PH、任务UID/view及随机流，不单独挖H。若某类有合格任务但s全部退化，记录DEGENERATE_SCALE并以空H将该类PH质量全部给原W（0.5），三模块按同任务规则完成且报告该预定退化；不能声称完成有信息困难挖掘。若某类无合格任务，记录覆盖不足，不能临时改困难定义。无合格任务时导出三臂no-op、完整配对和NOT_EVALUABLE回执。

在任何辅助头训练前，先以完整frame身份资格做源覆盖预检（不依赖分数/H）。正常训练覆盖最低要求：至少2个device各有合格正常任务；攻击至少2个device各有合法自身参考攻击任务。达不到记任务覆盖NOT_EVALUABLE，不将donor补成第二台，也不启动无解释力训练。足够覆盖但难样本无实际FP仍可训练排名任务；最终若无可纠正FP，效果检验NOT_EVALUABLE。正式头FIT拟合太好导致困难不足要如实报告；辅助view已经固定纳入，不能再加第三辅助头或换分组。 两辅助头完成且分数seal后，再作一次固定“有限残差信号”检查：辅助view中至少2个device各有≥1个合法自身参考、s>0且m>0（即r>0）的正常query；报告全任务及H内r>0行数、层级权重质量、设备/协议/组件数，并分别列正式/辅助view。此门槛只检查是否存在最低限度的真实修正目标，不以top20%排名自动证明H有信息。若不足（含全体r=0），记录SOURCE_SIGNAL_INSUFFICIENT，不训练三个模块、不换分组/头/阈值，导出明确NOT_TRAINED的三个no-op臂并完成预登记配对；有合格目标FP时无收益仍判FAIL，没有任何合格目标FP才判效果NOT_EVALUABLE。辅助头已完成的成本与结果保留，不自动重跑；三个模块未训练不能标COMPLETE训练终点。

## 6. 损失、采样和固定终点

设m_j=(score_j-t_j)/s_j，u_j=m_j-0.25a_j；不截断损失中的m，只截断网络输入。每任务仅一个score；s=0的任务不产生梯度，但保留抽样/审计计数，不删掉后重新分配view质量。

- 正常query：FIT内有限残差目标 `r=1[m>0]*clip(m+0.01,0,0.25)`；`L_N=(0.25*a-r)^2+0.01*(0.25*a)^2`。不高于FIT伪阈值的正常目标为0，避免对全部已正确正常持续奖励减分；0.01仅是冻结的规范化边界余量/成本系数，不来自CAL。该目标不能保证跨过真实CAL cut，收益由最终配对测定。
- 攻击query对每合法bank b：`L_A,b=softplus(-u_b)+(0.25*a_b)^2`；取 `L_A=max_b L_A,b`。并列bank稳定字典序，防止非确定梯度。攻击原来未检出仍保留，不只训练已检出的攻击。
- 总目标是按P0或PH抽样的上述query损失均值；不再乘一次层级权重。无额外损失项、对比学习、目标自监督、在线适应或H动态更新。

每步256 query，按对应分布有放回抽样；每次抽取(query,view)任务，只计算其一个头的已冻结分数；不再执行头梯度。三个臂共用numpy Generator(PCG64(27))产生的1,024,000个float64 Uniform[0,1)随机数，按step/batch位置消费；任务按(view顺序正式=0/辅助=1,query UID)排序，以float64累积CDF、最后值置1、searchsorted(side=right)逆CDF抽样。相同随机数因分布不同所取UID可不同；HARD/QUERY_ONLY分布相同所以逐任务必须一致。攻击bank在该batch全枚举，用分块控制内存；最多源六设备同协议候选，不能随机抽1个代替最坏保护。正常/攻击样本重复次数仅影响优化，不增加独立任务计数。

AdamW(lr=0.001,betas=(0.9,0.999),eps=1e-8,weight_decay=0.0001)，梯度global norm clip=5。float32网络，禁AMP；确定性算法，CPU四线程，默认CPU运行。每臂固定4000 optimizer updates，合计12000；无early stopping、学习率搜索、最佳checkpoint或第二seed。最终checkpoint就是update4000；每100步仅记录训练loss/梯度/elapsed，CAL不得参与checkpoint选择。保存step0及最终模型；不保留“挑最好”的候选。训练统计按固定步报告，不要求loss达到某值。L_STANDARD与L_HARD唯一差异是采样质量；L_QUERY_ONLY与L_HARD唯一差异是输入mask：槽14..45及47置0，保留query q14、FIT分数槽46、protocol槽48..49。三者网络形状/参数数/初始化一致；query-only仍保留同资格mask、任务view、H、抽样UID序列、最坏攻击bank枚举、cap及更新预算。计数是参考信息也须mask；不能改成全查询可修正。该对照检验具体参考关系信息增益，资格mask本身仍含参考可用性。

## 7. 最终CAL阈值与λ

基础头真实阈值沿用已验收原SOURCE_CAL正常、1%预算、strict `>` 的seed27 cutoff；须精确回放其校准算法/值/正常UID及权重身份，不重新挑阈值。t_j是FIT训练伪阈值，绝非该真实cut的替代。头变更时按原CAL算法重新校准该头，再做以下步骤。

每个学习臂用最终完整FIT t/s和封存模型，对**完整CAL攻击**及全部同协议因果合法LEARN参考bank枚举评分。λ逐一测试0/0.05/0.1/0.25；候选通过当且仅当每个bank下，正式seed27单头相对自己的未修正基线均无新增攻击漏检。每个候选只与正式seed27的真实cut比较。选择所有通过者中的最大λ；不看CAL正常收益打破选择，不用A/B调整λ。零候选必回放相等，否则数值异常。三臂独立λ，算法完全一致。

CAL攻击与源参考component交叉为零是硬身份条件，沿用v3保护合同；UID和原FIT/CAL隔离同样硬检查。所有攻击保留，候选库不足行回退。报告每λ新增UID数/配对数、合法对数、正修正对数、可达撤回margin数、最小margin/cap、每bank覆盖；未检出的原攻击也计入总分母。

若没有任何合法CAL攻击对，或没有任何基线已检出且可修正的CAL攻击对，则λ强制0，状态 `PROTECTION_UNINFORMATIVE`，不得把空保护最大λ当安全证据；仍完成配对no-op评价。存在合法对但都远离阈值可按规则选λ，同时报告饱和/不可达保护，不能称目标安全得到证明。λ=0或保护后正常收益归零是科学结果，不允许降低保护要求。

固定v3对照独立运行原 `fit_geometry`、`fit_scales`、`choose_lambda`，完全用同一基础头/FIT/CAL和参考身份；它保留其原权重/半径规则。新模块不可强制借v3 λ，v3也不借新模块尺度。现有v3固定三seed接口不能用复制seed27绕过验证；允许新独立scalar适配重用geometry/单列scale和λ保护数学，须测试与原v3在真实三列输入下的seed27尺度、逐候选修正分数/撤回计数一致；不要求单seed选定λ等于原三seed+ensemble联合保护选定λ；v3本对照的λ保护只针对seed27，与当前主线一致，明确标记v3-seed27，不冒充原三seed+ensemble结果。二者预处理/结构不同，因此只解释整体方法差异。

## 8. 评价矩阵与成功/失败判据

主矩阵：QUERY_TAIL base、同头v3、L_STANDARD、L_HARD、L_QUERY_ONLY × A/CIC_DEV与B/UNSW_DEV ×既定OLD_BANK/B0/B1/B2。bank manifest及旧政策定义固定复用，OLD_BANK仅是库身份，不暗示旧算法；不得将旧A成功扩大成B成功，历史A成功真实但B曾攻击退化。主学习假设以B2为预先指定主要银行条件，其余是预登记完整配对，不按结果换主项。每个cell同UID/同序、同库、同cut、同原评价权重；仅正式seed27报告为主要指标。

三个学习臂各增加无需训练的EMPTY与WRONG_BANK控制：EMPTY必须全池bitwise base；WRONG在B2预算下固定错误device、同partition/protocol、完整截止因果合法且真实组件≥2。对每目标query，候选错误bank按key排序选第一个能匹配自身合法参考行数和distinct component数的bank；在供体所有满足恰好N行/C个真实组件的合法子集中，取排序UID元组字典序最小的子集（N/C为自身合法行数/组件数）；实现可用剩余组件容量可行性检查逐UID决定，不需组合穷举。仅真正不存在可行子集才试下一个供体，不能贪心先选组件后失败就误称无供体，保留供体完整截止。若精确匹配不可得，该行控制NOT_EVALUABLE并保留在控制清单，不能借未来参考、跨partition或复制组件。供体计划只看metadata，评价分数产生前seal；报告可配对覆盖以及对应正常自身bank子集表现。错误bank控制不是所有目标行都必然可评价，不以它替换主完整分母。EMPTY无需λ重校准；WRONG用原该臂λ，不借控制成绩重调。

每cell同时报告：完整正常FPR（池级/逐设备及原层级权重、原始计数）、基础头TP/原FN、新增FN UID、攻击recall及原门槛、可修正正常FP总数、改正数、完整回退分解。按device/protocol/activity或攻击模式/capture分组，含零样本说明；可修正子集收益和完整池达标分开。另报两个不重叠的正常FP下界：资格外基础头FP数/完整正常N，以及资格内且 `score-cut>λ*s` 的cap不可达FP数/完整正常N；二者相加是该有界减分算法的完整池FPR条件下界。边界等于cap不算必不可达（strict >判决可恰好跨界）。同时报告按实际λ*a仍未纠正的FP，不能和前述下界混为一谈。低误报目标仍为池级1%、逐设备2%，攻击沿用原合同；这些目标不因本先导自动降低。

预登记判断：

1. 每学习臂的攻击门槛是所有主矩阵cell、正式seed27头相对自身base的**实测新增FN=0**。这是有限样本门槛，非绝对零漏检保证。任何cell新增即该臂保护FAIL，但继续完成所有已登记配对。
2. 学习式收益：在B2的A和B分别不恶化正常seed27 FPR，至少一池严格改善，且逐设备不恶化，且通过(1)；相对v3也列完全相同配对差分，不将base改善自动说成超过v3。因纯减分理论上不应新增正常FP，若反向出现先查实现/数值身份。
3. 困难任务价值：L_HARD通过(1)，相对L_STANDARD在A/B的B2均不恶化、至少一池严格降低正常seed27 FP（原权重与原始数均报告），任何设备不以恶化抵销；否则困难加权价值FAIL/NO_INCREMENTAL_GAIN。不以某一个单头或银行胜出替代。
4. 参考归因：WRONG若同样有效，结论收窄为一般纠错/参考无特异性证据。L_HARD还必须相对L_QUERY_ONLY，在A/B B2分别不恶化、至少一池严格降低正常FP且通过攻击门槛，才支持参考关系输入提供额外作用；否则标记REFERENCE_ATTRIBUTION_FAIL，不否定可能存在的一般纠错收益。query-only同资格mask，因而不证明资格本身的作用；不将单一消融声称为全部机制证明。
5. 若完整评价没有基础头误报且合法参考的正常行，改善问题NOT_EVALUABLE；有这种行但无收益、λ归零或攻击退化是FAIL，不伪称材料不可评价。源覆盖不足和保护无信息分别报告，不汇成PASS。

所有A/B结论标记开发环境证据。更广泛泛化/独立确认需另有未参与开发材料，本轮不发明新测试域。

## 9. 资源预检、异常停止及运行界限

默认新训练5终点/seed27：两个辅助头各40*ceil(N_G/256)更新、三个小模块各4000共12000更新；零新正式头、零前端重提取、零自动扩矩阵、零自动重跑。实现完成不等于允许运行。重计算只能在独立空闲资源窗口、确认现有单重worker不受抢占后执行；不远端查进度、不改变现有队列、不新购资源、不提交HPC。

实现必须提供resource_plan，仅用shape/文件大小估计：原E3 mmap，不复制全部794列；50维float32两view输入如全存约FIT×2×50×4字节，攻击多bank还要乘合法bank数，默认按batch动态生成/分块缓存，禁止无预算展开全query×bank×head×50。记录数据读取量、输出上界、峰值RAM预算、磁盘余量、CPU线程及预计训练时长范围，区分估计/实测。注册新阶段进程树RSS guard为8GiB；执行环境资源硬上限可沿用已有16GiB封顶、CPU四线程、单重worker，不新增资源或并发。原LEARN.npy mmap本身约2.27GiB，实际触页计入RSS，不能把mmap等同不占内存；metadata、PyTorch运行时、临时数组、缓存及子进程也计入。源装配、训练、评分各自估算并记录峰值RSS，预计任一阶段越过8GiB guard先记RESOURCE_NOT_READY，不能压缩样本/删query以过检。输出上限2GiB；两个辅助头各wall-time上限4小时、三模块合计2小时，新训练累计上限10小时；不得声称此处已有吞吐实测。

获准执行后的资源预检仅允许合成输入前向/反向，不产生真实训练模型；用固定50个warmup+200个计时step估算完整更新成本，实际源bank数量取已封存装配计数。预计峰值>上限、预计任一阶段或累计训练超过上述各自上限或磁盘剩余不足输出上界的2倍，记RESOURCE_NOT_READY，不减少步数/换GPU/挤现有worker。另报告装配、已有头回放和评价的独立I/O/时长估计，不能把它们藏进训练吞吐；若实测越过预算，停止留现场，零自动续跑。

身份、角色泄漏、UID顺序/数值绑定、非有限值、因果矛盾、参数hash漂移、确定性回放失败、资源越界均为EXCEPTION_STOP：写异常回执、最后成功stage、输入hash、错误堆栈及已完成产物；不自动换seed、丢坏行、修输入、resume或覆盖已有输出。不得把此类中断算科学FAIL。科学FAIL不终止登记配对；若后续另有技术异常才停。目标异常调查也不能借机选择新科学配方。

## 10. 必要工程验证与产物合同

实现在独立 `runs/learned_onboarding_v1_20261023/` 下完成：`src/` 新代码、`config/` 冻结配置、`results/` 只供后续获准运行；该目录当前不创建运行内容。不改旧v3/head的已验收文件，原准备审计六文件保持SHA。至少提供以下测试，先小型fixture后源只读装配验收；真实训练尚未获准时不得借验证启动拟合。

- 角色/UID乱序、缺失、重复、错误reference partition、源重叠的负例必须失败；q14误用26列、非有限、越界、E3零范数失败。
- timestamp相等、frame相等、同捕获未来参考、完整库截止晚于选中两条、bank_end_frame冲突、单组件复制、目标pre-bank例外/源禁止例外，分别覆盖回退或异常的正确分支。
- 两代表来自不同真实组件且UID稳定；参考顺序置换不改结果；不同协议不混合；50维顺序和2177参数数一致；参考改变能改变关系输入，q14不被投影丢弃。
- 分折传递闭包无交叉；FIT外标签/数值改变不能改变t/s、H、抽样或权重；训练源码/访问审计证明CAL/A/B未进入fitting，不靠shape测试代替。
- 普通/困难初始化、预算、损失一致；两类质量均0.5；多bank不放大query质量；H边界并列确定；同seed合成短训练可重放；query-only与hard除输入mask之外逐任务一致。
- λ=0/空库/不合法行bitwise回退；减分非负且≤λs；基线已有FN保留；strict `>` 等于cut必须判normal；最坏donor可否决自身bank通过的候选；空CAL保护强制λ0。
- 固定生产路径保存/加载模型、尺度和参考计划后分数bitwise一致；λ=0及空库回退仍bitwise。生产新模块/辅助头推理query batch=256（尾batch按实际行数），参考计算block=64条、bank按完整key字典序逐个处理；参考按UID排序，E3内积沿固定768列顺序，q14均方沿固定14列顺序，float64几何与最终减分/strict判决，网络float32，运行依赖/BLAS实现/四线程设定写入manifest。跨参考block合并只更新固定排序的代表，不改变归约或UID并列规则；现成头的历史回放继续使用其原验收生产路径，不为统一batch而改它。
- 分块等价测试改变query batch或参考block时，不要求任意BLAS路径的每个浮点逐bit相同：新网络/辅助头分数用atol=1e-6、rtol=1e-6，float64几何用atol=1e-12、rtol=1e-12；同时必须严格保持资格、代表UID/组件、H集合、最终decision及新增FN UID集合不变。任何代表或判决/集合翻转均为数值异常，不能用“在容差内”豁免；保存两路径差异现场，停止而不临时放宽容差。源验收与目标回放分stage，不能为方便一次打开全部池。

最低产物（每件含schema/version、status、输入hash与spec SHA256；数值未知的现在不填写伪值）：

| 产物 | 必须内容 |
| --- | --- |
| `implementation_manifest.json` | 新代码hash、依赖版本、测试结果、spec hash、NOT_RUN/执行状态；本文件不是该产物 |
| `input_binding.json` | 基础头/checkpoint/cut/norm/feature/q14/spool/各bank清单精确路径+hash、ordered UID；resolved/missing明确区分 |
| `source_tasks.parquet`或分片NPZ+JSONL | query UID/原slot/role/label/device/activity/capture/session/component/group/fold、正式/折外分数、每view头身份/分数与每合法bank的资格与两代表UID、原因及完整截止 |
| `source_task_receipt.json` | 完整分母、真实frame资格、各类设备/组件覆盖、任务门槛、源UID无交叉；更新证据不能覆盖旧结构审计 |
| `fit_statistics.json` | 两折及完整FIT的t/s、权重规则/UID hash/quantile定义、degenerate标志 |
| `hard_tasks.jsonl` + `sampling_receipt.json` | H UID/难度/fold/组/边界/质量，以及每view/组m>0的真实FIT伪阈值FP数和H内占比（排名H不是必然误报）、P0/PH hash、随机流seed及hash |
| `resource_plan.json` | 上述内存/I/O/输出/时间估计、合成预检与资源状态，不能冒充训练实测 |
| `AUX_G0/`、`AUX_G1/`、`L_STANDARD/`、`L_HARD/`、`L_QUERY_ONLY/` | init/final权重、配置、训练log、实际更新数及资源、最终endpoint回执；无best模型选择 |
| `calibration.json` | 真实cut身份、FIT部署t/s身份、全部λ/最坏donor/seed27保护计数及选定λ、信息性状态 |
| `control_plan.json` | EMPTY与WRONG的固定metadata供体、精确匹配/不可评价原因及计划hash |
| `predictions/<pool>/<bank>/<arm>` | 完整ordered UID、base/corrected seed27分数、cut/decision/eligibility/reason/两代表UID/实际减分；足够重算配对 |
| `paired_summary.json`、`decision.json` | 全矩阵、分组指标、FN UID差集、预登记判据逐项PASS/FAIL/NOT_EVALUABLE、开发证据范围、automatic_promotion=false |
| `EXCEPTION_STOP.json`（如有） | 异常分类、现场、未完成cell、零自动重跑声明 |

允许Sol解决文件封装、保持已冻结生产batch/归约顺序的向量化及缓存等纯工程选择，不允许静默改变头、seed、参考资格、输入、损失、H规则、终点、λ、主银行或判据；科学修改另起V2并解释原因。若现有接口信息不足，记录缺失身份/字段并停止相应stage，不用猜测补齐。完成实现后交付可审查代码及验证回执，再按实际授权边界决定执行；此处没有排队或后台训练。
