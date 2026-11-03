# 历史正常参考 C1 超算交付

本目录仅构建交付副本，原科学包保持原样。用户“允许下一步”授权交付、环境验收与一次 C1/P-DEVONLY 实验：4CPU、16GiB、8小时，无自动重试或训练。

运行 `python build_delivery.py --tshark /usr/bin/tshark` 生成 `staged_root` 和 `DELIVERY_INPUTS.json`。构建首先验证原代码封印及全部输入 SHA；仅映射基础 EXECUTION.json 的路径，远端代码清单同键且只有该配置 SHA 变化。原配置和原封印保存在 `provenance`。大数据仅登记原 D 盘路径，不复制。

按 DELIVERY_INPUTS 的 local_path 上传至独立 incoming 根下的 remote_relative_path。不得直接覆盖共享远端目录。上传清单和 installer 后，先运行 `install_delivery.py --manifest <清单> --incoming <incoming根> --destination /public/home/jiangxinwei.zr/work/paper04 --verify-only`；全部验证通过再去掉 `--verify-only`。任何已有文件不同即报错，不覆盖，不自动清理冲突。

安装后仍须验收 Python3.11.11 / NumPy2.0.1 / Torch2.5.1 私有 overlay、依赖、tshark、完整源码身份及 `run.py check`。模板仅提交一次，DEV 门失败停止。进度服务监听127.0.0.1:18785，由 Codex 右侧查看同步回来的真实 STATUS.json。

`remote_preflight.py` 为远端准备好的只读验收：核全量交付 SHA、授权与环境脚本；按 Slurm 模板初始化 modules/overlay，核精确版本、实际依赖导入、56项生成数据测试和材料 READY。输出独占的 `remote_preflight/` 及持久日志/回执，不做真实模型前向或包解码。

`submit_once.py` 仅在上述验收 PASS、封印及授权未变、输出与科学尝试标记均不存在时允许一次固定 sbatch。发送前独占落盘 `SUBMISSION_LOCK.json`；调用超时、回执异常、进程中断均视为提交结果未知，禁止重试。真实执行前由操作者确认用户已释放电脑控制；本地准备脚本本身不运行远端命令。
