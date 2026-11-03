# Edge Linux 预检作业包

结果：本目录准备一个可独立解包的工程预检交付；只有 `BUILD_RECEIPT.json` 产生后才表示实际归档已完成核验，不代表 Linux 门通过。
影响：选择规则、UID 封存、脚本、原冻结运行时文件与权重同包；不重复装入三份原 PCAP，不启动全量评价。
下一步：交付前由 Claude 复核；在既有 Linux 运行时执行一次有界预检，取回回执后再锁定全量预算。

包是单独的 `edge_preflight_checkout/`，不要解包覆盖现有超算项目。代码、配置与资产保留原仓相对路径及字节。`PACKAGE_MANIFEST.json` 登记每个文件大小/SHA；`PACKAGE_CONTRACT.json` 登记新查询封存、当前小切片、原包文件名/大小/SHA及边界。完整原包须已经在远端个人/项目存储中，或另行按其 SHA 上传。包内选中 UID 清单不等于本次会编码全部清单：本次只跑 `ACTIVE_SLICE_CARD.json`，最多100个端点。

## 本地构建（无模型载入）

构建命令由 Codex 在选取产物封存后执行：

```text
python -X utf8 -B runs/edge_linux_preflight_package_v1_20261103/build_package.py --selection-dir runs/edge_query_selection_v1_20261103 --selection-seal <该目录中的实际封存JSON> --slice <已封存的实际预检切片JSON> --output <新的edge_linux_preflight.tar绝对路径>
```

归档输出不可覆盖。它采用固定 tar 元数据，以同一批文件字节重复构建得到相同归档；`BUILD_RECEIPT.json` 另记构建时间，不放入归档。真正的交付归档必须经过脚本内的逐成员字节复核。构建不读取外部质量分数，不安装依赖，不训练，不提交云端。

## 超算执行（先等交付前复核）

1. 上传 `edge_linux_preflight_20261103.tar` 及旁路 `.tar.sha256` 到新的远端交付目录，进入该目录，执行 `sha256sum -c edge_linux_preflight_20261103.tar.sha256`。
2. 执行 `tar -xf edge_linux_preflight_20261103.tar`，然后进入 `edge_preflight_checkout`。
3. 只填四个实际存在的远端路径：

```bash
export EDGE_PYTHON='/实际已有环境/bin/python'
export EDGE_TSHARK='/实际已有tshark-4.6.6'
export EDGE_RAW_DIRECTORY='/个人或项目存储/三个原包所在目录'
export EDGE_OUTPUT_BASE='/个人或项目存储/新预检结果父目录'
sbatch runs/edge_linux_preflight_package_v1_20261103/preflight.slurm
```

不自动选择分区、账户或安装依赖；如本校要求账户/分区，按既有有效账户追加到 `sbatch` 命令。Slurm 固定1 CPU、6GiB、10分钟、不重排队。外层只给预检包装进程最多540秒，给身份核对及终态写盘留余量；包装入口见 `PACKAGE_CONTRACT.json` 的 `preflight_entry`，它追加每个必测形状的严格singleton探针，原预检/encoder文件保持原字节，探针也计入逻辑编码上限100。没有自动重投或通过后自动全量评价。

## 需要取回

- `edge-preflight-<jobid>.out/.err`；`$EDGE_OUTPUT_BASE/edge_preflight_<jobid>/DELIVERY_RESULT.json`及`DELIVERY_STATUS.json`（若调度器先硬停，后者保留最后阶段）。
- 同目录 `RUNTIME_IDENTITY.json`、`preflight_supervisor.log`。
- `real_slice/RESULT.json`及旁路SHA、`STATUS.json`、`ENCODING_BATCH_LEDGER.jsonl`、若存在的`CLONE_FAILURE_DIAGNOSIS.json`、`worker.log`。失败也完整保留。
- 同一 `real_slice/` 中的 `STRICT_SHAPE_PROBE_SUMMARY.json`、`STRICT_SHAPE_PROBE_LEDGER.jsonl`、若存在的 `STRICT_SHAPE_PROBE_FAILURE.json` 及旁路 SHA。

合格状态同时要求外层 `LINUX_PREFLIGHT_PASS`、内层 `SAME_RUNTIME_REAL_SLICE_E2E_PASS`、`final_linux_runtime_gate_pass=true`及singleton探针汇总`PASS`；仅归档验证通过不能替代它。构建时强制核对所选人口的完整`SHAPE_CENSUS.json`、扩充切片及选择封存的SHA连接，并核算“切片端点＋额外形状探针≤100”。这证明元数据覆盖，实际Linux数值门仍须等待运行。全量流式续跑worker、预算与正式评价授权仍须另行闭合。
