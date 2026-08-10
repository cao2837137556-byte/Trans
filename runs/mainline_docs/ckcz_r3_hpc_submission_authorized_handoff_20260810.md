# CKCZ r3 正式 HPC 提交授权（2026-08-10）

状态：**USER AUTHORIZED — READY FOR ONE FORMAL AMD SEED-27 SUBMISSION**

## 1. 授权事实

在 Kimi 对本地真实输入彩排给出 PASS（commit `978fbe1`）后，用户于 2026-08-10
明确回复“我授权啊”。该回复解除 CKCZ r3 的最后一道人为提交门。

## 2. 唯一授权对象

- archive：`issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3_upload_bundle.tar.gz`
- archive bytes：52,581
- archive SHA-256：`0f68b154f0d2c45cc5520e25746d30a273a096a8026cf0df6fdbb1c1d8e9d59c`
- bundle commit：`6ec2686f690ab29021f9b5225b8c8d469bbd9e42`
- partition：`amd`
- seed：27
- formal bootstrap：200 reps
- submission switch：`CKCZ_SUBMIT_AUTHORIZATION=YES`

该授权只允许 installer 经过 bundle SHA、冻结输入 SHA、cache 在线、22 项合同测试、真实
lineage coverage 和 `sbatch --test-only` 全部通过后，幂等提交一个正式 result-producing job。

## 3. 不在授权范围

- r1/r2 bundle 或 job 的任何重提；
- Intel 重复副本；
- seed 37 / seed 47；
- cooler-motor 或其他 FINAL 输入；
- 修改 prereg、erratum、allowlist、分母、frontier、verdict 逻辑或 family-specific patch；
- 把 `sbatch` 接受、heartbeat、CPU 占用或未终结文件当作实验成功。

## 4. 成功与失败边界

正式成功必须同时满足：

1. 进入命名的 `diagnostic_real_inputs` 阶段；
2. progress sequence 持续产生已完成单元，1,200 秒无进展 watchdog 未触发；
3. 真实诊断退出码为 0；
4. 200-rep post-result validator 通过；
5. Slurm 最终状态为 `COMPLETED`；
6. pullback archive 与 sidecar 生成并通过 SHA-256；
7. 拉回后再做独立审查，才允许解释唯一科学 verdict。

任何启动前、lineage、存储、watchdog、validator 或 packaging 失败均为工程失败，不构成
科学结论；必须保留 control/log/progress 证据并在再次提交前归因和增加永久回归门。

## 5. 当前状态

授权已记录，但在用户于 HPC 终端运行正式 installer 并获得新 job ID 之前，不能声称已经提交。
Codex 负责交付精确的上传、正式提交/监控和 pullback 命令；用户执行后把完整输出交回。
