# UNSW 下载完成与核验启动环境修复

两份固定官方PCAP于2026-09-26 06:45:07 UTC（北京时间14:45:07）全部下载完成，总计7,020,234,000字节。V4期间出现一次传输异常并自动恢复，无需再次人工干预。完整本地文件大小及SHA再次核对通过：

- benign：4,145,381,196字节；42c8c8444ab6d2a50170e8aee7012436fe2ce877d40f026b07614972f06ca808。
- mixed：2,874,852,804字节；befc3f6882a2b3137652a81af1deba4f71d3cbd4b80db6344c2d64a9fc112bed。

这证明下载所得文件与已记录字节摘要一致，不替代发布者独立签名或后续结构/语义核验。记录见acquisition/receipts.json。

自动衔接在06:45:15 UTC报QUALIFICATION_STARTUP。qualification.log证实qualify_once.py导入旧模块时因dpkt缺失失败；原因是continue_v4继承下载器的sys.executable，使用了Codex随附Python而非已冻结Python3.9。execution目录尚不存在，真实PCAP检查和TShark均未开始。此为助手启动实现错误，不是数据或科学失败。

保留原qualification.log和失败状态快照，新增qualify_after_download_py39_v1.py，显式使用原27项pins中的C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe，并验证运行时散列。未安装新包或修改原qualify_once.py、协议、参数、模型。原dpkt1.9.8可用；在该Python3.9.13上重新运行8项原合成检查全部通过，包括生成PCAP的真实TShark检查。两份完整文件SHA、原27项pins及8处无关修改均通过。

新控制器要求原导入失败证据相符、execution不存在、排他启动目录及独立新日志；它只启动原核验程序一次。旧失败属于原始读取之前的启动失败；实际原始核验尝试1、原始解码重试0。qualification_startup_repair_acceptance_v1.json及11项repair pins已封存，旧下载程序不再启动。

真实核验于07:30 UTC开始，后台会话11152，控制器PID44380；第一份文件进入SOURCE_SHA_AND_STRUCTURE。已授权的原链继续执行，仍限5GiB父进程+TShark与6小时，真实异常停止。没有模型前向、训练、校准、HPC或科学规则变化。

根status.json/dashboard.html及execution/status.json为当前入口。下载状态resume-v4的100%为已完成历史阶段，不能当核验完成。最终输出仍是execution/result.md、summary.json和SHA256SUMS。被动首小时可用性、五台完整保留、标签仅候选、ACTIVE/E3独立性未证实、旧FAIL和独立ID NOT_RUN边界不变。

启动后快照：

{
  "status": "RUNNING",
  "stage": "CAUSAL_INPUT_AND_ANNOTATION_CENSUS",
  "capture": "unsw-benign-20180528",
  "completed_captures": 0,
  "total_captures": 2,
  "elapsed_seconds": 89.01600000000326,
  "utc": "2026-09-26T07:32:00.318000+00:00",
  "retries": 0,
  "model_forwards": 0,
  "packets": 401408,
  "total_packets": 5413239
}
