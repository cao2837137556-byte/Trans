# 局部参考几何 v2：实现包

本包实现唯一冻结方案 [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)，方案 SHA256 为 `797a08dc7cd540f6c1c2d498490e520cb40d6938da8c6ceec350f5b80b17fc51`。原方案保留其定稿时的 `DESIGN_FIXED_IMPLEMENTATION_PENDING` 快照，当前工程状态及验收证据以 [IMPLEMENTATION_RECEIPT.json](IMPLEMENTATION_RECEIPT.json) 为准。

入口为 `run.py`，默认 `check`。操作步骤、预算、输出和停止条件见 [EXECUTION_CARD.md](EXECUTION_CARD.md)。真实源实验与候选 A/B 尚未运行，合成验收和只读输入核验不代表科学效果。

| 文件 | 职责 |
| --- | --- |
| `lg/geometry.py` | 冻结的局部半径、1C/2C资格、D0/L共享距离与整库因果检查 |
| `lg/source.py` | 六头RAW重放、own-FIT前向、两折D0及唯一L源诊断 |
| `lg/metrics.py` | 两种ensemble算术、累计攻击账本、原分母精确门槛 |
| `lg/target.py` | 源通过后主CAL复现及零撤回检查，再一次两池评价 |
| `lg/runtime.py` | CPU/RSS/墙钟/距离对/输出限制、阶段回执及前序门控 |
| `DEPENDENCIES.json` | 原核心、历史适配器和清单的内容绑定 |
| `tests/` | 小型人工数据与模拟依赖的验收，不调用真实科学计算 |

当前实现计算登记总体的全部支持，不启用可选的support=1判定裁剪。D0和L共享距离；三seed共享geometry/support。原B1结项与独立源Atomi 1C延期保持。
