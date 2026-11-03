# 现代检测头交付修订 v1r1

2026-10-18。落实独立审查P1–P7。旧v1归档和结果证据保留，本目录是新的待运行版本；真实实验NOT_STARTED。最终本地验证状态、测试选取和继承项见 `validation.json`。

## 本次修复

- **P1**：LightGBM允许合法自然停止，endpoint与日志分别记录requested_rounds、callback_iterations、effective_tree_iterations和native_stop；仍固定请求500轮，无early stopping或目标选型。本地4.6.0常数特征测试为500次回调、1轮实际树，所以“回调必少于500”并不成立，少树与少回调分别报告。
- **P2**：新增 `--heads-only` 与 `--modules-only`。头阶段只要求完整QUERY_TAIL产物；入网六库仅在M阶段成为必需输入。M读取同包封存的九终点及头评价，只运行事前指定TabM、LightGBM的四库配对，不重训。
- **P3**：复用回放证据来自adapter实际数组比较，包含每池每seed/ensemble的score/decision摘要、UID顺序、dtype/shape及SHA。先完成共享只读前置校验再登记REUSE_VERIFIED；缺证据或条件不兼容明确记录后重训，seal/hash/非有限权重损坏仍硬停。执行期只捕获专属ReuseIneligible，不笼统吞异常。
- **P4**：模块endpoint核验同时要求CAL_used、DEV_used、reference_used均为false。
- **P5**：现代头合同的applies_to文字明确涵盖每个family的每seed与ensemble；数字门槛和评价算术不变。原QUERY_TAIL合同字节保持。
- **P6**：M返回后显式断言optimizer_updates==0，缺字段或非零均拒绝。
- **P7**：提交及作业入口在模型Python启动前检查extra_deps目录与dependency_install_receipt.json；缺失直接提示运行离线安装，不自动联网安装。

## 固定科学比较与运行边界

MLP_QUERY_BCE、官方TabM0.0.3、LightGBM4.6.0；同782维输入、同FIT/CAL划分及权重，seeds27/127/227。神经头40轮、batch256，TabM k32/3blocks/width512/dropout0.1，LightGBM请求500轮。所有阈值只用源CAL正常样本，strict score>cut；外部ensemble仍为三seed float64 mean-logit。固定TabM与LightGBM接OLD_BANK/B0/B1/B2，不按目标结果选开关。

推荐两次顺序作业：先 `--heads-only` 完成P/T/K并产生 `runs/modern_heads/HEADS_COMPLETE.json`；入网资产就绪后 `--modules-only` 读取其绑定的heads/SHA256SUMS。头产物不可变，模块另存；第二次不重新执行P/T/K。模块失败不自动重试，保留heads与独立module_status。也保留默认full整链入口，full仍须预先具备入网资产。

MLP通常仍需重训，因为原QUERY_TAIL未强制记录完整numeric_runtime指纹。按最多九个新终点准备，不把支持复用等同于已省训练。

## 资源、环境和交付

维持8CPU/16GiB、单重阶段/4线程、RSS保护14GiB；P/T/K与M各自使用相同保守资源上限。72h Slurm/70h内部时限是**每次作业**上限，分两次运行不再表示共享一个70h预算；不代表真实ETA，不缩训练配方。旧预算直接继承，只有合同绑定随新版本更新。分阶段导出使用不同名称，不嵌套上次归档；所有真实结果与封存头继续保留。

依赖仍为目标Python3.9/NumPy2.0.1/Torch2.5.1及包内离线新增库；LightGBM轮子要求Linux x86_64/glibc>=2.28。本地合成环境NumPy2.0.2/Torch2.8.0不同，目标兼容和完整真实资源峰值尚未核验。

操作见 `OPERATE_HPC.md`。本轮只做本地合成/交付验证；没有上传、提交、真实训练或新增性能结论。三设备回归尚未接入，整套系统不得PASS；零新增漏检仍是验收要求，不是实现保证。
