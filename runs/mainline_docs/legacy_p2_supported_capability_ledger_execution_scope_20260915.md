# 固定旧 P2 有效输入能力账本：本次执行范围

2026-09-15。用户在“先补齐固定旧模型能力表，必要时复用封存分数或固定模型评分”的说明后回复“那就下一步”，并要求核对四个 OOD 是否参与训练。本次授权用于该固定基线账本。随后用户要求系统性补学历史路线，与本任务并行，不取消基线工作。

执行前配置：`runs/legacy_p2_supported_capability_ledger_v1_20260915/scope.json` 及 SHA。目标是解释旧系统已有能力；不新增训练、优化器、阈值选择、新数据或 E3 前向。

## 输入与唯一执行

仅七个已列旧 stage 工件：fit/select plan、report plan、旧 P2 report scores 所在容器、fit/select E3 embeddings、report E3 embeddings、旧 probe state 和 threshold-freeze marker。路径与已有 SHA 在 scope 中逐项固定。源目录为 `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/`。

- 复用旧 P2 的 262,050 条 report 判决/概率/缺失状态。其他 G0/P1 行及 C1、CKBQ、M7 数值不解释、不输出。
- 从原缓存选择性读取 197,268 条 report 有效表示，另取 2,188 条熟悉正常 select 和 760 条原 ID fit 有效表示，共 **200,216 条**，只通过固定原 P2。
- 缓存中未选表示字节仅透明跳过，不转换数值数组；不调用读取全部旧表示/所有 probe state 的历史执行器。只加载原 mean/scale 和 P2 四个参数数组。
- 原完整账本保持：report 262,050（有效 197,268）；熟悉正常 7,000（有效 2,188）；ID fit 809（有效 760）。缺失不统一解释为协议不支持，也不计为内容识别能力。
- 原阈值仍为 float32 sigmoid 输出拓宽至 float64 后，与概率 `0.065159872174263` 作 `>=` 比较。旧 report 的原判决为主结果，新评分判决必须逐 UID 一致，否则停止。

重新通过小 P2 的原因是旧保存的概率可能因 float32 sigmoid 饱和形成并列值，未保留完整 raw logits。本轮事先同时约定：原概率与 raw logit 两种经验排序诊断均输出，不能见结果后挑指标。原固定阈值结果不变，不能把补出的 raw logit 曲线叫训练增益。

低误报诊断对熟悉正常、hydraulic、street、predictive、stream 五池取最差池 FPR，分别限制 1%/0.1%；整数误报预算、同分整组、无插值，允许全不报警端点。ID fit 不加入阈值曲线。它们是已暴露开发数据的描述，不是独立校准后部署指标；不输出新部署阈值。

攻击按旧完整 18,398 fit 中的精确族名支持、69 条阈值 support 的族名接触，以及原 role/tier/source 分层。不能拿新重放 11,529 的族集合替代旧模型已有训练经历，也不能把 ToN 扫描/暴破与其他来源不同名称说成必然全新机制。

原 report 中已经披露的 sealed_final_attack 和 sealed_final_ood 保留旧角色名，作为开发复评范围明确列出；真正保留的 cooler-motor、seed37/47、其他未列 viewed/FINAL 不打开。旧 select 分数文件、新 CIC CHECK 模型分数、原始 PCAP、新数据特征和 E3 模型不进入本次执行。

## 验证与终态

在真实执行前，合成验证选择性行读取、非 P2 数值跳过、角色/UID 身份、归一化 float64→float32、原阈值边界和最差池同分处理。独立审查通过后锁定执行器 SHA。每个目标最多通过固定检测头一次；异常停止、零自动重试，失败不覆盖或伪装成科学结论。

持久 `status.json/status.md` 保存阶段、完成量与异常，结果包括分池/分族/曝光/覆盖表、两种低误报点、固定 P2 分数和终态核对。只使用现有本地 CPU，4 intraop/1 interop、float32、无 AMP；不做资源试验，不启动 HPC，不安排 LLM 轮询。

此账本独立于尚未启动的增强双臂方案。本次得到的基线不改变该方案的 seed、损失、分母或旧历史判定。系统性历史补学另外记录来源与覆盖缺口。
