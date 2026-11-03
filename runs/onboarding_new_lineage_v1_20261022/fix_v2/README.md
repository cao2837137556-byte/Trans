# 2026-10-22 入网解码运行身份修复

v1 在 `raw-CIC_DEV` 停止，`DECODER_STDERR` 是唯一直接原因。解码器退出码为 0，stderr 仅 66 字节：

```
Running as user "root" and group "root". This could be dangerous.
```

旧封存解码器要求 stderr 必须为空，故正确地拒绝了本次运行环境输出。此前的小型生成测试和真实头回放不执行真实 TShark，没有覆盖云端 root 身份路径。本次补充真实解码验证。

修复只在新部署层：raw 子进程切至现有 nobody 用户 uid/gid 65534、清空附加组；仅新运行的 raw 输出父目录归该用户。`WIRESHARK_CONFIG_DIR` 指向新运行内 root 所有、只读的空目录，避免继承 `/root/.config/wireshark` 的权限错误。未改变 HOME，未扩大任何输入权限，未修改原始解码器或屏蔽 stderr。

验证 `PASS.json`：93 项生成回归测试通过；A/B 各 64 个真实包、全部 56 字段，root 与修复后输出逐字节一致，修复后 stderr 为 0、退出码为 0；普通身份的完整 Python 导入也成功。TShark 全部离线解码首选项相同，唯一例外是未调用的 Cisco 远程实时捕获工具默认用户名 root/nobody，已显式记录，不影响 `-r PCAP`。

软件与输出使用独立 v2 路径；v1 原失败现场、归档、退出回执、已完成头回放证据保留。本次复用全部已上传原始捕获、完成的查询特征、检测头及冻结权重，无重新上传或百万查询特征重建；只重做尚未产出有效参考库的入网阶段。v2 仍执行自己的完整输入核验与头回放。

v2 unit：`paper04-onboarding-20261022-v2`。软件 `/srv/paper04/onboarding_new_lineage_20261022_v2`；run/state/export 分别沿用对应父目录下的 `onboarding_new_lineage_20261022_v2`。资源仍为 8 核 / 16 GiB，无 swap；没有自动重试或自动停机。

正式修复后验证：CIC 全量 **645,951 个包**已完成，`raw_receipt=COMPLETE` 且 stderr 为 0；实际越过原失败位置并进入 `raw-UNSW_DEV`。完成凭据在 `CIC_raw_complete.json`，真实运行身份与解码器摘要在 `decoder_execution.json`。

18764 页面已切换到 v2，普通监听脚本 `track_onboarding_v2.py` 60 秒同步。终态结果独立保存为 `pullback_v2/`、`final_state_v2/` 和 `RESULT_BACKUP_VERIFIED_v2.json`，不覆盖 v1 证据。
