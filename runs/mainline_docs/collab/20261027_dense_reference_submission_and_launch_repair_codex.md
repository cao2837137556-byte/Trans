# 密参考 r2：179523 提交与启动故障回执

**后续最新：用户已确认修复版并提交179536，启动修复通过；原104数值门8条失配而停止。** 见[179536执行回执](20261027_dense_reference_repair_restart_and_numeric_stop_codex.md)。本文件中的“待修复版一次提交确认”为179536之前的历史状态。

2026-10-27。用户最新指令为“你操控电脑提交上去吧，我懒得动手了。按照之前的方式就行”。这是已授权前三阶段的一次提交执行回执；不是新的效果结果。

## 实际执行与明确结论

**179523 / node185：FAILED，exit 1:0，运行 00:00:03。异常停止在启动前 `package_sha`，尚未执行合成测试、真实前向、原104门禁、补编码或密源CAL。** 无新误报率、召回率、A/B评价或训练结果。完整目标矩阵仍因第三池冻结资产缺失而阻断。

Codex 复用了 VS Code 的既有 `school-hpc` 登录通道，将 r2 归档上传并部署到 `/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_matrix_v1_20261027`。归档115,876,260字节、完整SHA及1492文件Python校验通过；通过 `sbatch --export=NONE hpc/run_dense.slurm` 只提交一次。原授权4CPU/16GiB/12小时、CPU-only、零自动重试保持。原BASE/CTX及18769终态保持。

证据：`runs/dense_reference_matrix_v1_20261027/deployment/{DEPLOY,SUBMIT,MONITOR,LAUNCH_FAILURE_EVIDENCE_179523,REMOTE_BUNDLE_INITIAL_179523}.json`。远端日志和原失败目录保留。封存r2清单SHA仍 `ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120`；归档SHA仍 `43c31bd5ba3dc169aa95fae0079f2b856801043c46fd7862736110cb603b0140`。

## 已确认的根因及额外集成缺陷

1. 实际触发故障：`PACKAGE_SHA256SUMS` 的1492行使用CRLF。部署Python按记录解析可以通过，但原Slurm直接运行GNU `sha256sum --check`，把每行末尾的CR保留为文件名字符，1492项均报不存在。`package_sha.log` SHA为 `b48e13d43a435efce5ea852abb2239886ca39ad69fe45447eb4d25ba7803f673`；末行 `WARNING: 1492 listed files could not be read`。`launch.json` 记录stage=`package_sha`、returncode=1，`tests.log`未创建。这是启动脚本的兼容性问题。
2. 修复审计发现的后续确定阻塞：原Slurm将科学输出设在原包的 `runtime/job_ID/science` 内，而冻结 `src/chain.py` 明确要求 `FRESH_EXTERNAL_OUTPUT_REQUIRED`。即使只修换行，后续也会停止；这是代码静态核查结论，尚未运行到此处。

原86项合成测试及独立封包验证没有覆盖这两处实际Slurm集成问题。本轮采用独立修复层保留科研封包，补足对应回归验证，不通过放宽文件SHA或原104数值门规避。

## 修复范围与当前进度

独立目录：`runs/dense_reference_launch_repair_v1_20261027/`。固定原manifest/launcher/授权身份；只兼容清单记录的LF或CRLF终止符，继续逐文件SHA与完整成员集合核验；输出改到修复层的独立 `runtime/job_ID/science`。环境、算法、冻结编码器、输入、原104逐字节门、三阶段顺序与资源合同保持。增加准确启动阶段及失败行回执。

**当前：修复完成、独立审阅及超算端只读验收均PASS，已部署，但未提交第二个作业。** 修复层封条SHA为 `12bac486285b6cbaa0a58df7c8ded17dc6c1a74d79632f2ff7763e33f4c34300`，共5个封存代码/文档文件加清单，批准模板仍为false、授权新提交数0。原launcher另固定SHA `8b1db4d33924736a901627237d6d272249537aee36b4b134aa4134bce183968d`，原实际批准文件SHA保持 `0576a803faf1fd77ffb57fecb606e5a31aa98957b895f657c23fb152ff2c4b26`。

本地21项测试为20通过、1项因Windows原生symlink权限跳过；受控symlink拒绝另有覆盖。**超算node168端21/21全部通过、无跳过**；真正运行GNU校验器复现旧CRLF失败，修复校验通过同一份未改原字节，内容篡改仍拒绝。Bash语法、缺少科学完成回执时非零退出、冻结chain拒绝包内输出/接受包外布局的合成集成均通过；合成集成在空包预检即停止，不读真实模型或源数据。原包1492件及修复层5件全部SHA通过。回执：修复层 `validation/LOCAL_VALIDATION.json`、`validation/REMOTE_READONLY_VALIDATION.json`；远端完整合成测试日志SHA `e0b00a0de682d8f50873663906e575e4d730462b26027bdd9972ac8f5d39f3d1`。本轮临时部署/179523状态桥已停止，Windows终态页面仍运行，不再访问远端轮询。

### 修复版一次提交的具体申请

拟执行：仅一次新 `sbatch --export=NONE runs/dense_reference_launch_repair_v1_20261027/run_repair.slurm`，仍amd1节点/4CPU/16GiB/12小时、CPU-only、0自动重试。仍只运行 `runtime → encode → source_cal`；无训练、无A/B新评价、无正式目标矩阵。预计5–8小时仍仅规划区间；真实ABI、原104严格逐字节门与实际吞吐仍未验证，任何技术异常停链保留。

原执行卡明确“异常停止、不自动重跑”，且原一次提交授权已用于179523，因此新提交待用户明确确认。确认后仅创建独立私有修复授权，绑定上述两层封条与原批准文件；先O_EXCL一次提交锁，再提交并保存新job ID；不得再调用原部署器的旧`/submit`。新进度桥必须绑定修复层 `runtime/` 与新job/token，原179523缓存和失败目录保留，18770页切新job并明确保留历史。批准模板或合成测试授权不得用于生产。

## 用户可见进度

新页 <http://127.0.0.1:18770/> 已启动并核实显示“异常停止”、179523、具体换行根因与“未开始补编码或源CAL”。原始远端bundle另存，页面缓存的中文诊断是基于固定路径只读证据的本地注释，非伪造远端科研进度。终态后普通同步器自动退出，页面离线保留，不持续调用AI轮询；Windows辅助程序隐藏运行。

下方文档中的“等待手动上传/未提交”属于此次实际提交前的历史快照。最新状态以本回执和根 `IMPLEMENTATION_STATE.json` 为准。
