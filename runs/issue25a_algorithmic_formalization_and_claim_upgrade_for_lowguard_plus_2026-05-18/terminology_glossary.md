# 术语表

- benign-OOD drift：非攻击流量因环境、时间、设备或业务变化而偏离 ID benign 分布。
- attack-side shift：攻击样本在家族、时间窗口或特征形态上偏离少量 confirmed supports。
- low-alert budget：部署允许的 OOD benign high-alert 上限，例如 1%。
- OOD-safe feature：在提高攻击分离的同时不会显著推高 OOD benign tail 的特征。
- attack-separating feature：能区分 confirmed attack supports 与 benign/OOD benign 的特征。
- source_rich representation：比 original100 更丰富的可审计流量统计表示。
- confirmed attack support：经确认的少量攻击样本，用于部署阶段适配。
- kcenter coreset：以覆盖攻击训练池 feature space 为目标的支持样本选择方法。
- guarded adapter：训练时显式纳入 OOD benign guard 的少样本攻击评分模型。
- threshold calibration：使用 ID calibration 与 OOD validation 在目标 OOD alarm budget 下确定阈值。
- locked validation：不参与方法选择的固定评估对象，用于验证候选方法。
- consistency check：已参与方法发现或背景验证的设置，只能用于一致性报告。
- strong baseline pack：面向审稿防御的强基线集合，包括 few-shot anomaly、semi-supervised anomaly、modern tabular/IDS baselines。
