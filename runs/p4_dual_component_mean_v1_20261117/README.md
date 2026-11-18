# Paper04 双组件正常支持度对照

本轮比较 v12 表 9 的两个 3D-Ref 评分方案。两组共用开发对照库、790 维 MLP、三空间半径、种子 27／127／227、原扣分尺度、λ=0.25、p=4、SYN 无 ACK 旁路及源阈值。CIC、UNSW、Edge 各有 8,863、66,082、4,124 条参考，共 388,202 条查询。所有原始评价权重按 UID 顺序绑定。

联合距离先在每条合法参考上计算，再在每个不同组件内取最小值。参考开放、几何可用且第二个组件距离严格小于 1 时，A 使用较弱支持度，B 使用两个支持度的算术均值。两臂分别对聚合后的支持度使用同一四次修正函数。距离缓存的字段、实际读取路径和 SHA 记录在两个阶段的 INPUTS 回执中。

AMD 计算节点先运行独立的 45 分钟上限预检。预检复现三池的冻结判决和指标，重新解码三个已有 CIC 正常短采集并重放原三行编码批次，将重建向量用于真实小切片。各池均逐记录直接枚举合法参考，核对组件最小值、严格准入、两臂评分、旁路、评价和回执。正式作业在预检成功退出并通过回执校验后提交，申请 4 核、12 GiB、2 小时上限。两份调度回执记录实际耗时和资源。

正式结果首先列出每组的正常误报撤回数和正确攻击告警撤回数。CIC、UNSW 各分完整和建档后视图，Edge 保留正常、HTTP、UDP 及有总体分母的 HT 指标。所有种子和集成都做逐查询子集核对。超算 artifacts 目录保存距离、匹配组件、逐行分数和改变判决的 UID。ARTIFACTS 回执记录位置和 SHA。

本地从项目根目录运行本目录的 pack.py、verify_local.py 和 delivery.py command 即可重建包、回归回执和启动命令。delivery.py 使用既有 SSH 隧道上传和回传，dashboard.py 在本机 18812 端口提供进度页。本轮接收程序的启动命令在页面内可直接复制。最终可转发段落在 received/RESULTS_FOR_PAPER.md，各分组计数在 received/HEADLINE.csv，本地重计和回传核验在 received/LOCAL_ACCEPTANCE.json。

[本轮交接](../mainline_docs/collab/20261117_paper04_v12_dual_component_mean_support_handoff_codex.md) · [冻结输入](FROZEN.json) · [本地回归](LOCAL_VALIDATION.json)
