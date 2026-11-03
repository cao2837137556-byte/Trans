# UNSW 单文件诊断授权与启动

用户对第一份文件一次诊断、最多15分钟/5GiB、不训练模型的提议明确回复“允许”。新授权已写入decoder_diagnostic_authorization_v1.json，关联计划SHA f2410cac941dd6418a1f0bf234ee7928db96b6c93e5db4ddd5d7b8ef96c6be84。原计划false及原失败保持历史，未原地改写。

只读benign第一份文件，最多5,413,239包/900秒/父子合计5GiB，自动重试0。不读取第二份PCAP，不新增数据/模型/训练/校准/HPC/角色/参考库。TShark字段/命令、Census和因果逻辑保持，仅补资源/退出/列形状证据。

启动前13诊断pins、27原pins、70原失败证据文件及8处无关修改SHA全部核对一致；分支和HEAD保持。沿用5项合成检查，无重复资源试验。独立代理只读确认字段/命令/三项对账保持，提醒区分资源终止、自然退出和读者清理。

已启动会话41243；根status/dashboard及decoder_diagnostic_execution_v1/status为当前入口。每5秒采样RSS并非操作系统即时硬限额。结束后只解释并封存此诊断，不自动接完整核验或训练。

快照：

{
  "status": "RUNNING",
  "stage": "DECODER_DIAGNOSIS_FIRST_FILE",
  "capture": "unsw-benign-20180528",
  "packets": 2023424,
  "total_packets": 5413239,
  "elapsed_seconds": 143.875,
  "utc": "2026-09-26T11:25:03.149297+00:00",
  "model_forwards": 0,
  "diagnostic_decode_passes": 1,
  "automatic_retries": 0,
  "full_qualification_complete": false
}
