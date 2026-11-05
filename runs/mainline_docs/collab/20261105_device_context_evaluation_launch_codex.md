# 四组固定模型评价执行回执

结果：用户“允许运行。”后，独立评价包 v1 已启动；真实预检作业 182427 已运行，尚未宣称预检或科学效果通过。
影响：固定九个已验收训练端点与 OLD782，复用源域 CAL 阈值和 FIT 尺度，开始 A/B 防退化及已消耗 Edge 诊断评价。
下一步：普通程序依次执行 PREFLIGHT → CONTEXT → AB → EDGE；工程错误停止，科学指标失败完整报告，不筛选或自动重训。

## 口径与资源

- 三个新组 REFIT782 / STATS8 / FUSION790，加 OLD782；每组种子 27、127、227 及集成。STATS8 只报告 RAW，其余 RAW 与 C5_P3。
- 保持原 768 编码器、q14、源域归一化、CAL 阈值、参考几何、p3/λ=.25/SYN guard；新头使用已封存的各自 FIT 尺度。
- A/B 报告完整视图和原有主评价窗口，复用已冻结的 UID、权重和基础支持；旧 RAW/C5 必须复现。源 CAL 攻击组与正常误报另外检查。
- Edge 固定 60,000 查询及 4,124 参考。因果 8 维按 D1 当前包包含、单调前缀时钟、逻辑抓包重置计算，禁止排序或外部拟合；全量检查 checkpoint 恢复。
- 真实预检覆盖原包解码/独立统计 oracle、原始完整批次重编码与输入指纹、合法完整参考库距离、四组评价和正式报告函数。小切片性能不作为模型选择依据。
- 依次使用 1 CPU、8 GiB；PREFLIGHT/CONTEXT 各 30 分钟，AB/EDGE 各 60 分钟上限；不自动重试。总墙钟上限 3 小时（不含排队），不是耗时预测。
- 固定 A/B 防退化、C5 安全性以及 RAW/C5 裕量分布。检出不佳不会阻止其余注册组报告。Edge 已被诊断消耗，不能称未接触外部确认集。

## 已完成核验与交付

本地回归逐条复现 A/B 1,312,808 个旧 C5 判定，同时验证零支持、SYN guard、条件权重分母和科学失败报告。仅代表本地回归；Linux 真实门仍独立执行。

启动复用用户当前 SSH/SOCKS 通道；没有建立新登录。新目录 `/public/home/jiangxinwei.zr/work/paper04/runs/device_context_evaluation_v1_20261105`，与训练和原评价隔离。普通程序自动提交、显示进度、取回小回执并检查执行完整性；大数组、模型和分数留超算。工程验收与效果验收分开。

证据：[执行合同](../../device_context_evaluation_v1_20261105/EXECUTION_AUTHORIZATION.json)、[交付 SHA](../../device_context_evaluation_v1_20261105/DELIVERY.json)、[本地回归](../../device_context_evaluation_v1_20261105/LOCAL_REGRESSION.json)、[启动回执](../../device_context_evaluation_v1_20261105/STARTUP_RECEIPT.json)。进度页 http://127.0.0.1:18806/ 。
