# K8192 统一参考库执行入口

结果：原准备作业 183971 在 UNSW 小切片编码入口失败。列表和元组的序列化比对错误已修复，并在 TP-Link 与 Motion 各 16 条真实解码快照上通过本地回归。超算重新提交及进度以本地 `LOCAL_PROGRESS.json` 为准。

影响：按冻结卡 acfe0a1 使用每设备 × 协议 K=8192、固定 C4 盐和零退化硬线。现行 P4_MAIN 与既有结果照旧，候选产物单独保存。

下一步：修复链复用已核验的 Motion 原包和索引。远端程序在真实预检和准备作业验收后提交唯一一次正式重放。

- 进度页 `http://127.0.0.1:18809/`，本地 `LOCAL_PROGRESS.json` 保存最近的现场回执。
- 工作入口 `pack.py`、`run.slurm`、`worker.py` 和 `dispatch.py`。修复记录见 `FAILURE_AND_RETRY.md`，修复包清单见 `PACKAGE_MANIFEST.json`。
- 本地真实检查枚举 CIC 六段短片，得到 Eufy 675、HeimVision 289 个合法端点。TP-Link 和 Motion 的真实包切片分别通过端点、原包序、时间和 context8 校验。本地 Python 缺冻结编码器运行依赖，E3 端到端核验由既有超算运行环境完成。
- 正式输出 `RESULTS_FOR_PAPER.md`、`RESULT_INDEX.json`、`ACCEPTANCE.json`、指标及配对表、变动 UID、输入和候选 SHA、资源回执，由程序按 `RETURN.json` 核验后放入 `received_repair_183971`。`received` 保留 183971 的失败回执。
