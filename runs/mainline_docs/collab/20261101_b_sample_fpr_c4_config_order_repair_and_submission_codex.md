# C4 配置序列化故障修复与提交回执

2026-11-01。状态：PASS_REPAIR_AND_SUBMISSION，超算作业 **180526** 已实际 RUNNING（node185）。当前没有 C4 科学结果。

前次并未提交实验：预检已确认 Python 3.11.11 / NumPy 2.0.1 / Torch 2.5.1 正确，随后 CONFIG_SEMANTICS 失败。根因是 build_delivery 写入远端配置时 sort_keys=True 重排了嵌套字典，而既有 semantic→digest 保留字段迭代顺序。JSON 参数值完全一致，却得到不同校验值。

本次仅将远端配置恢复为原参数的原字段顺序。原失败配置、STATE 和预检回执保留；修复前严格确认尚无提交锁、编码锁或科学输出。修复前后 JSON 值相等；本地重现原失败、验证恢复后语义哈希匹配，并检查已有提交会阻止此修复。模型、选点、容量、盐值、λ、执行卡及全部科学源码均未改变；2,405,307,756 字节原包/索引全部复用，零重复上传。

超算重新预检：输入哈希通过，23/23 工程检查通过（0.812 秒）；随后 sbatch 返回 180526，已观察到 RUNNING|node185，工作进程进入 TP Link 的 CHRONOLOGICAL_COPY。前次为提交前失败，本次是该候选首个真实超算编码作业。

执行目录仍为 `runs/history_sample_coverage_c4_execution_v1_20261101/`；本次修复部署目录为 `runs/history_sample_coverage_c4_deployment_repair_v1_20261101/`。原部署目录 SUBMIT_RECEIPT.json 已登记真实作业号并指向修复部署。右侧进度继续使用 http://127.0.0.1:18789/，无需用户另开页面。

程序继续按原合同自动更新进度、取回、历史校准门、一次 A/B 和独立验收。已确认提交和进度正常后结束本轮，不持续 AI 监测；最终科学结论以执行目录 FINAL_ACCEPTANCE.json 为准。

机器回执：`runs/history_sample_coverage_c4_deployment_repair_v1_20261101/REPAIR_ACCEPTANCE.json`。
