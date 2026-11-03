# 179602 完整新增科学结果只读拉回

固定作业179602，读取原job目录；不训练、不模型前向、不评价、不提交Slurm。

导出包含job中全部新科学输出、编码库、tensor回执、源CAL候选统计、环境及控制日志。仅固定排除 `science/readonly_view`（已保存输入的硬链接）和 `science/runtime/numpy201`（安装的NumPy依赖），其资产/环境身份回执仍包含。排除目录记录在manifest，不是缺失的新科学产物。任何意外 `.private` / bootstrap / client 文件停止而不导出。

远端导出目录独立于原job，导出前后完整选定清单及逐文件SHA须一致。原始与压缩上限各4GiB。loopback 18785，沿用户既有认证SOCKS连接，一小时限时服务，不创建新SSH会话、不输出token、无自动重试，partial保留。下载先验证压缩包SHA和精确tar文件集，再解包并逐文件重验SHA及终态身份。

`prepare_bootstrap.py`只在本地准备 `bootstrap.command.sh`，不会连接服务器。父代理通过现有VS Code终端执行一次准备好的命令后，`download_results.py`完成下载及验收；本目录测试只用合成数据。
