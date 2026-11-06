结果：v1预检182502因PyTorch线程重复初始化失败；独立v2修复和正/负路径回归通过，真实预检182507运行中。
影响：正式训练尚未开始；方法、数据、损失、种子、轮数及资源未改变，旧失败保留。
下一步：v2真实全链路→真实训练/校准/预算门→三种子正式训练→源CAL；无已知故障时由普通程序继续，外部效果待评价。

# 2026-11-05 源域分数锚定运行时修复v2

方法与用户接受既有A/B取舍的范围，见[设计执行卡](20261105_fusion_score_anchor_launch_codex.md)。v2沿用v1的SPEC、anchor_train、anchor_diagnostics、test_anchor逐字节原文；只修正运行时初始化并增加故障回归与独立交付。

- v1作业182502：FAILED/1:0，3分07秒，MaxRSS 858544 KiB；在真实输入核验后、FrozenBackend构造时第二次调用torch.set_num_interop_threads(1)，被PyTorch拒绝。未产生编码/训练通过回执、正式头0。没有可复用科学输出；187秒包含输入读取等工作，缺少子阶段计时，不能虚构精确有效/浪费拆分。
- v2：DECODE_PREFLIGHT由既有FrozenBackend独占interop初始化；训练进程由入口配置一次。没有吞异常、跳真实编码或降低验收门。
- `test_thread_ownership.py`用独立真实PyTorch进程覆盖旧重复路径拒绝、新解码路径通过、新训练路径通过；本地已PASS，并成为Linux重交前置检查。另保留原λ=0逐字节回归等检查。
- v2真实预检182507，amd、1CPU/8GiB/30分钟，随后自动训练门和三头40轮。正式单头预算60分钟，按真实训练计时预测超预算即停；工程失败不自动重试。当前尚未声称真实门或科学效果通过。
- 仍仅拟合源FIT/CAL，全部固定种子报告，不改变C5、不凭Edge挑模型。大数组/逐轮头留超算；小回执自动取回。

当前执行目录：`runs/fusion_score_anchor_v2_20261105`；旧失败目录：`runs/fusion_score_anchor_v1_20261105`；日志审计：`runs/fusion_training_audit_v1_20261105`。进度：http://127.0.0.1:18806/。验收时先读新目录CHAIN_STATE、STOP/RESULT和scheduler，不能沿用本文启动时状态。
