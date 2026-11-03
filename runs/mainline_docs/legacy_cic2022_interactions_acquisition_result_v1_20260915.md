# CIC IoT2022 正常交互获取与对照材料核对

日期：2026-09-15。状态：`ACQUIRED / INTEGRITY_PASS / NAME_CORRESPONDENCE_FOUND / SUPPORT_NOT_QUALIFIED`。

## 本次结果

用户在攻击包获取完成后授权继续取得对应正常交互材料并核对采集方式、标签。本轮已取得官方 `3-Interactions.tar.gz`，完成留存、完整性检查、全部成员元数据核算、内部README阅读，以及与攻击包的设备名称对应。没有解码PCAP、生成模型输入、推理、训练、评估或HPC。

这一步解决了“只有攻击包，没有对应正常主动业务材料”的获取问题。它没有证明逐流标签可靠、正常/攻击采集条件可比，也没有产生模型效果结果。主线保持增强固定旧E3/P2，新设备入网随后；统一前端/GRU暂缓。

## 已取得对象

来源：<https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/download.php?file=3-Interactions.tar.gz>。

| 项目 | 实际结果 |
|---|---|
| 压缩字节数 | 76,776,437，约73 MiB |
| SHA256 | `3ae44cb001b1ffc7001c360bab31ffe7683f4ba14e86ef5d946e81296ba9a468` |
| 项目留存 | `runs/legacy_cic2022_interactions_acquisition_v1_20260915/raw/3-Interactions.tar.gz` |
| 下载原件 | `C:/Users/28371/Downloads/3-Interactions.tar.gz`，保留 |
| 检验 | gzip CRC/长度与tar完整遍历通过；不安全路径、链接均0 |
| 展开常规文件总大小 | 89,482,240 bytes；没有全量展开落盘 |

复用已登记浏览器，未重新登记。普通AX点击产生 `ERR_BLOCKED_BY_CLIENT` 页面；专用 `downloadMedia` 返回但未见落盘；随后用文档支持的下载事件监听与精确链接点击成功接收单个对象。没有复制Cookie、改变安全设置或绕过订阅。后续同类下载应使用已验证的下载事件流程，避免误把文件当网页导航。

复用了上一阶段的 `inspect_archive_metadata.py`，只运行本正常包一次。流式解压读取全部字节以验证完整性，解释的是成员头和一个2,641-byte内部README，没有解释PCAP内容。SHA是本地对象身份，未取得官方发布校验值。

## 实际清单与对应关系

归档共1,227项：349个目录、878个常规文件。876个 `.pcap` 后缀成员中，12个以 `._` 开头，各4096 bytes；扣除后是 **864个普通PCAP文件候选**，共89,430,447 bytes。没有验证魔数、实际包数或内容去重，不能把候选数当作可训练流数。

普通候选分布：Audio 132、Cameras 128、Home Automation 598、Other 6。39个设备目录有候选流量；Netatmo Weather Station目录只有一个0-byte `No Interaction Experiments.txt`，内部README也明确没有该设备交互实验。不能将论文摘要所述60台设备、官方设备表40条和本包39个有流量的设备目录混为一谈。

291个活动目录中，284组各3个普通候选；7组数量例外：HeimVision/WAN_PHOTO、Eufy/WAN_WATCH、Eufy/WAN_RECORDING、Luohe/WAN_WATCH、Home Eye/WAN_PHOTO各2个；Luohe/LAN_WATCH、Home Eye/WAN_RECORDING各1个。没有重复成员路径，但尚未证明文件内容不重复。

13个攻击设备目录名称都能找到正常目录候选。`Gosund Plug - Roomba` 在两包中名称相同，但官方设备身份仍有多解；不能据目录相同消除歧义。其余12项也是暂定名称对应，不是已经验证的受害端点或正常—攻击配对。

| 第一优先候选 | 普通正常文件 | 普通RTSP实验文件 | 具体正常业务 |
|---|---:|---:|---|
| Amcrest | 9 | 6（Hydra 3，Nmap 3） | LAN拍照、录像、观看，各3次 |
| SimCam | 9 | 5（Hydra 3，Nmap 2） | LAN拍照、录像、观看，各3次 |

其他已对应正常目录包含ArloQ、HeimVision、Borun、Luohe、Netatmo、Atomi、Eufy、Globe、Philips Hue、Ring。完整逐组清单、名称对应与字节数见本run的 `metadata_assessment.json`；不凭目录名断言实际传输协议。

## 采集方式与标签核对

正常内部README说明Physical、LAN、WAN、Voice四种交互方式；摄像机的Photo、Recording、Watch分别为拍照、录像、观看。这提供明确的预期正常业务来源，而不是仅凭“未匹配攻击就当正常”。但它没有端点地址、精确时间段、逐流标签或逐文件采集位置，也不能证明每个背景连接都是干净负例。

本轮读取的[官方介绍](https://www.unb.ca/cic/datasets/iotdataset-2022.html)在Network configuration节描述一台双网卡Windows机器，一侧接网关、一侧接交换机，Wireshark监听两个接口；Dataset节说采集经过网关的IoT流量。攻击内部README则明确写在攻击机捕获。

**当前存在一般采集说明与攻击专门说明的视角差异，不能认定两类文件观测条件相同，也不能直接认定无法比较。** 需要检查实际端点可见性、方向、报头完整性及潜在双接口重复。正常内部README没有消除该问题。

[数据集论文](https://ieeexplore.ieee.org/document/9851966)的公开摘要、引言预览与目录可读；Data Collection Process、IoT Vulnerability Attacks的正文需订阅，本轮未读到。没有绕过访问控制，也没有把摘要当完整方法证据。官网摘录和访问范围保存于 `official_capture_method_evidence.json`。

攻击内部README仍只提供LOIC、Hydra/Nmap等实验来源，没有精确攻击标签；RTSP实验还包含之后尝试直播的行为。不能把所有RTSP流或整份攻击PCAP都标为攻击，不能用当前模型分数猜真值。

## 接下来做一次小范围原始输入语义核查

**取得两包后，不再把继续找更多数据或写更多获取方案作为默认下一步。** 下一步对象已落实为两个摄像机的23个文件：

- 正常12个：Amcrest、SimCam各取LAN_WATCH与LAN_RECORDING的全部三次。
- RTSP实验11个：上述两设备Hydra/Nmap的全部现有普通候选，保留SimCam Nmap只有两次的事实。
- 合计82,607,797 bytes，约79 MiB。其中正常文件合计147,358 bytes，攻击文件合计82,460,439 bytes。

精确成员路径、归档SHA、成员大小与清单索引已写入 `proposed_two_camera_semantic_probe_scope.json`，没有提取/打开这些PCAP。该范围是待核查的材料名单，不是训练/测试分母，也不是每类12/11条学习样本。选择依据为此前固定的设备线索、正常观看/录像与RTSP相关业务；未查看模型表现来挑文件。

这些正常文件非常小，最小录像候选只有1,414 bytes。大小本身不证明可用或不可用，但不能把文件名的“观看/录像”当作已经包含足够持续流量、完整连接或旧E3因果前缀。

下一步实现并审查一个限定23文件的读取器，检查：PCAP格式/链路类型与捕获完整性、MAC/IP端点对应、时间与双向会话、是否能满足现有旧输入条件，以及攻击操作和正常业务的标签依据是否可恢复。它不训练、不调阈值、不计算模型表现，不自动加入Flood或其他原始包。文件内容也未必能弥补缺失的实验记录；不能承诺读包后必然取得精确真值。

若必要端点、标签或可比观察条件无法建立，应明确这些材料不足以支持本次条件排序增强主张；不能通过弱化标签或换分母把“不合格”改成“合格”。如有可辩护的狭窄子集，先明确该子集的依据和局限，再冻结训练增量。数据角色与依赖组件须在训练目标生成前划分，继续保留同一前瞻输入范围、范围内失败、范围外覆盖和因果前缀规则。

本轮用户授权范围内的获取与元数据核对已完成；上述具体包级步骤尚未实现或执行，不由此文件自行授予执行权限。已有下载授权持续有效，不新增重复的笼统下载审批。

## 验证与状态

已核对成员计数/字节数、7组次数例外、设备名称对应、23文件范围与来源SHA；更新交接顶部与实验索引，保留上一阶段封存报告。既有8个无关修改按此前保存的SHA核对不变。未重跑攻击包扫描、历史实验、合成测试或资源试验。

solved: 正常交互包取得并封存；13个攻击目录的正常名称对应建立；明确23文件下一步范围。
changed_mainline: no。
active_blocker: 端点/标签/采集可比性与旧输入兼容性仍未经包级验证，训练支持尚不合格。
frozen: 旧E3/P2资产、历史协议/判定/分母不变，无训练或HPC执行。
superseded: 对应正常交互包未取得/大小未知；不替代已有科学失败或资格判定。
next_action: 实现并审查限定23文件的原始语义资格核查，明确执行范围后核查；无需再找更多原始包，不直接训练。
