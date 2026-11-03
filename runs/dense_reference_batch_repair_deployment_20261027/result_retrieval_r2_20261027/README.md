# 179602 只读拉回修复 r2

v1 在只读清点时拒绝一个模型输入符号链接，尚未生成结果包。v1目录与原实验现场保持，本目录是独立修复导出，不是重跑实验。

导出包含job中全部新增编码库、tensor回执、源CAL候选统计、环境及控制日志。仅固定排除三个既有输入/依赖位置：

- `science/readonly_view`：已登记输入的硬链接视图；保留资产绑定回执。
- `science/runtime/numpy201`：已安装NumPy依赖；保留环境回执。
- `science/encode/runtime/vendor/netFound-base/model.safetensors`：仅允许确切指向 `/public/home/jiangxinwei.zr/work/paper04/incoming_20261020/model.safetensors` 的符号链接。核对链接字面目标及编码RESULT中的冻结checkpoint SHA `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105`；不解引用、不复制权重。manifest记录相对位置、目标、冻结SHA及dereferenced=false。

任何其他符号链接和意外 `.private` / bootstrap / client 文件继续停止。导出前后完整选定清单及逐文件SHA须一致。原始与压缩上限各4GiB。loopback 18785，沿既有认证SOCKS，一小时服务，不新建SSH，不输出token，无自动重试，partial保留。

`prepare_bootstrap.py`仅本地生成 `bootstrap.command.sh`；父代理经既有VS Code终端执行一次后，运行本目录 `download_results.py`。下载完整验证压缩SHA、精确tar成员、逐文件SHA及终态身份，再保存回执。测试全部为离线合成数据；符号链接边界测试使用受控mock，不把Windows链接创建权限当生产策略。
