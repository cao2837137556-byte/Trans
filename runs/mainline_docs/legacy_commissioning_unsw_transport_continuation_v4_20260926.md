# UNSW V4：网络暂时故障的有界自动等待

原两份官方PCAP下载与一次原始核验授权延续。本次没有新增源、模型执行、训练、校准、HPC或科学重试。

V3于2026-09-26 05:27:01 UTC（北京时间13:27:01）停在73.06%，最后三次均为HTTPS握手超时，零字节、同一偏移983,296,673；旧脚本的连续三次无进展门槛导致退出。V2此前是连接拒绝，这次不是同一底层报错。数据核验尚未开始。网络归因仅能到连接/TLS层；不能证明是Clash或官方服务单方故障。

06:16 UTC并列只读HEAD诊断：现有代理路径和单次直连都返回原官方URL的200，长度2,874,852,804及ETag不变。直连只作诊断，实际续传仍用原系统代理，未调整VPN/Clash/系统设置。

已重新核对完整首文件SHA，混合文件983,296,673字节前缀SHA为891ff8dd1fd8fb315ca8c82f35ce133037aa295679819264e6f38c08afaa1a51。V2/V3共124条mixed分段记录逐条校验散列、连续覆盖和长度；包含零字节失败记录，不代表124份独立数据。全部原27项核验封存、V3 pins及8处无关修改保持一致。

新增transfer_resilient_v4.py和continue_v4.py，保留旧失败目录及原qualify_once.py。传输策略现在按暂时网络故障等待，15/30/60/120/240/300秒逐步退避，之后最多每5分钟尝试；每5秒更新倒计时。连续30分钟没有新字节停止；仍受原scope创建时起24小时总截止和400次新增传输异常上限约束。原科学零重试规则不变。HTTP范围/长度/ETag/编码不符、证书失败或本地数据改变仍立即停止。

已下载的完整首文件复用，仅续传第二文件缺失后缀。短响应只推进真实收到的字节；缺失响应部分不会凭声明长度跳过。界面区分WAITING_FOR_NETWORK和STOPPED_NO_RETRY，并显示last_byte_utc作为真实字节进度时间，utc仅为状态更新时间，monitor_updated_utc只是显示心跳。

Python3.9隔离集成夹具8/8通过：三次超时后恢复且字节/receipt顺序正确、短体从缺口续传、源ETag改变拒绝、超量响应拒绝、前缀篡改拒绝、原截止不重置、长期网络中断有界停止、证书失败立即停止。无网络或真实解码参与测试；本次为本代理代码审查，未启用子代理。145项新增传输pins封存。

启动已按顺序完成：首status出现且字节超过原断点后，才启动控制器。下载会话10434，控制器85979。当前入口根status.json/dashboard.html，内部acquisition/resume-v4/status.json；V3会话83384/32267已退出。原始核验仍在两文件完整后由封存qualify_once.py运行一次；execution/result.md才是核验结果，不把下载完成当模型效果。

启动后状态快照，后续请读取实时文件：

{
  "status": "RUNNING",
  "stage": "DOWNLOAD_BOUNDED_RANGE_CONTINUATION",
  "file": "unsw-mixed-20180601",
  "bytes_received_total": 5190019565,
  "bytes_expected_total": 7020234000,
  "percent": 73.93,
  "bytes_current": 1044638369,
  "completed_files": 1,
  "total_files": 2,
  "range_requests": 594,
  "transport_interruptions_total": 22,
  "transport_version": 4,
  "consecutive_no_progress": 0,
  "raw_decoder_retries": 0,
  "utc": "2026-09-26T06:24:11.671816+00:00",
  "last_byte_utc": "2026-09-26T06:24:11.671816+00:00",
  "retry_in_seconds": 0,
  "original_deadline_utc": "2026-09-27T02:41:08.425705+00:00",
  "elapsed_seconds": 110.875,
  "error": null,
  "monitor_pid": 43308,
  "monitor_updated_utc": "2026-09-26T06:24:14.678486+00:00"
}
