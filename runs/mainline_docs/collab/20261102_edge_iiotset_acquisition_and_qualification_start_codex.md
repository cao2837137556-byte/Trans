# Edge-IIoTset 三包已获取，资格检查自动进行中

2026-11-02（America/Los_Angeles）。用户授权：“允许，按三包卡做资格核验”。

三份固定原包已完整获取并验精确长度、ZIP CRC与SHA；正常包全量头部及独立capinfos核查已交给普通程序。尚不声称数据资格通过，更没有外部模型评价。

|文件|原包字节|SHA256|
|---|---:|---|
|DDoS HTTP Flood Attacks.pcap|28307602|`2fb2558d51defd1704a54a7a76df787048e9281d2efd8177703d66a7f78620ba`|
|DDoS UDP Flood Attacks.pcap|247560012|`6de0341f27093cac8a5eba657b8a49ecbac4dd5bf6c452a6274472df69172ce5`|
|Temperature_and_Humidity.pcap|345868816|`2b37027b1575f1d5bba7ab6cf87503df303ea2c9ab07a69b20f8d0f28696da6f`|

原包总计621,736,430 bytes；累计HTTP实体传输321,645,924/700,000,000 bytes。均在D盘受控目录，无C盘中转、无既有材料删除/移动。首次HTTP404是目录文件名未整体编码，修正同一获准文件URL后成功，失败回执保留。

两攻击全量229,142 / 3,215,732记录，容器/时钟/前后SHA及计数守恒通过；HTTP/UDP均指向192.168.0.128，受害MAC均dc:a6:32:fb:69:b5。HTTP有19,076个文档来源方向GET起始候选，UDP入向该edge共2,898,830条；它们仍是行为方向候选，不是认证逐包真值。反向响应单列；UDP随机伪造源不能只用论文四个IP筛，四IP仅命中4条UDP。

13项攻击角色基础核对只允许继续这一个固定正常核身份/时序，不是数据PASS，没有换目标/扩大下载。程序正常启动PID 31928，回执CONTINUATION_START.json、CONTINUATION_LAUNCH.json；扫描器5项合成检查通过。

当前证据目录：runs/edge_iiotset_raw_qualification_v1_20261102/。APPROVED_CARD绑定用户授权与原卡SHA，TRANSFER/TRANSFER_LEDGER是实际获取，HTTP/UDP_AUDIT与ATTACK_TO_NORMAL_GATE是已完成阶段。PROGRESS.md供人查看，最终以RESULT.json、CAPINFOS_CROSSCHECK.json、CONTINUATION_FINAL.json为准；程序自动写collab/20261102_edge_iiotset_three_file_raw_qualification_codex.md。尚未产生最终回执时不能称通过。

后续仅核正常全量、独立capinfos、同物理目标、实际7200秒与后段正常、真实先后。基础失败就停止；基础通过仍需标签/上下文与独立性复核。累计主动原包审计1800秒（已完成阶段保守预留250秒），不自动下载其他包或跑模型。默认扫描没有全量内容去重；可选dup工具4项合成检查通过但尚未扫原包，不能声称无镜像。

C5 p=3/A/B冻结保持，0E3/q14编码、0support/距离、0模型评价/训练/超算；原件与下载ZIP保留。不持续AI监测、不定时唤醒；普通程序自行更新进度和最终回执。
