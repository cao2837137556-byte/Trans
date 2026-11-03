# UNSW 同源断点续传 V3：连接恢复后的工程修复

用户原“核验”授权仍涵盖同两份文件的下载与一次原始数据核验。本次只修复传输，不新增模型实验、训练、校准、HPC、数据源或核验重试。

## 停止原因与保留内容

V2 在 2026-09-26 03:48:33 UTC（北京时间 11:48:33）停止，进度 59.55%。第二份文件最后三次请求均在偏移 35,383,969 收到零字节，错误为 ConnectionRefusedError(10061)，触发连续三次无进展保护。累计19次传输中断含此前两次，并非达到V2的20次新增中断上限。原状态、日志与分段证据全部保留。

第一份 benign 已下载 4,145,381,196 字节，完整 SHA256 为 42c8c8444ab6d2a50170e8aee7012436fe2ce877d40f026b07614972f06ca808，重新校验通过。mixed 已存 35,383,969 字节，其 SHA256 为 374d84a96a6ba5738386f61dde2cfbdcb7a210610ce1897fb5909415556dc990；8条分段记录逐条核对，含5条有数据和3条零数据记录，覆盖连续且散列一致。

05:10 UTC 的只读诊断显示当前系统代理127.0.0.1:7897可连接，原官方mixed URL返回HEAD200，长度2,874,852,804和ETag均未改变。日志不能追溯证明当时是代理进程还是上游端点拒绝；未修改代理、VPN或URL。

## 修复与验证

新增 transfer_resilient_v3.py 与 continue_v3.py，保留所有V2与原27项核验代码/元数据封存。先验证并重用完整benign，再从mixed首个缺失字节续传。仍采用8MiB范围、If-Match、HTTP206、精确Content-Range/Length/ETag及identity编码检查；只推进实际收到的字节数。

本次恢复最多20次新增传输中断，连续3次无进展仍停止；前两次无进展等待30/60秒，期间本地状态持续更新。24小时截止从原scope创建时间计算，不随恢复重置。此次有明确恢复连接证据，并非盲目重启旧失败执行器。

独立代理在隔离临时夹具完成20/20检查：完整文件复用、身份/路径/散列/长度篡改拒绝、零/短/完整体偏移、越界拒绝、错误HTTP/范围/ETag拒绝。未重新跑原始解码。原27项pins及V2 pins均通过，8处已有无关修改SHA一致。新23项transport pins含receipt、mixed旧分段、故障状态和诊断记录。

启动顺序已落实：先启动下载器，等首status存在且进度超过原断点，再启动控制器。下载完成后生成固定顺序benign→mixed receipts，原qualify_once.py仍只运行一次；execution不存在及日志排他创建防重复。下载/核验中的任何科学结果均未预先宣布。

## 当前入口

root status.json / dashboard.html 为用户入口；当前内部下载状态为 acquisition/resume-v3/status.json。V2 STOPPED是保留历史。后台执行会话transfer83384、continuation32267。真实raw核验尚未启动，最终输出仍为execution/result.md、summary.json及SHA256SUMS。无模型轮询或定时模型任务。

启动后状态快照（并非永久实时值）：

{
  "status": "RUNNING",
  "stage": "DOWNLOAD_BOUNDED_RANGE_CONTINUATION",
  "file": "unsw-mixed-20180601",
  "bytes_received_total": 4206193133,
  "bytes_expected_total": 7020234000,
  "percent": 59.92,
  "bytes_current": 60811937,
  "completed_files": 1,
  "total_files": 2,
  "range_requests": 474,
  "transport_interruptions_total": 19,
  "transport_version": 3,
  "consecutive_no_progress": 0,
  "raw_decoder_retries": 0,
  "utc": "2026-09-26T05:15:32.218194+00:00",
  "elapsed_seconds": 113.7039999999979,
  "error": null,
  "monitor_pid": 12776,
  "monitor_updated_utc": "2026-09-26T05:15:33.244561+00:00"
}
