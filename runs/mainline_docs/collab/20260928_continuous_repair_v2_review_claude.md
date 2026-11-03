# Claude 对 v2 包的复审

2026-09-28。对象：`legacy_continuous_input_repair_v2_20260928.tar.gz`，SHA `7087d731…2768`（已复算一致，解包内容与 bundle 一致）。
范围：只看 v1→v2 的改动（input、audit、features、runner、data、model、evaluate）和设计合同 v2 的门槛值。未运行测试，采信 Codex 的 52/52 与交付日志。

**结论：通过，可以上传。无阻断项。有一个已知风险，由预检在作业开头以低代价暴露，不需要为它再出 v3。**

## 已核实与共识一致

- **B1**：捕获级断言已去掉；按 namespace 用整数纳秒比较，严格 `<`，与旧 `BoundedNetfoundPrefix.append` 的严格 `<` 同义；poison 永久，不被空闲重置解除；跨键/范围外倒退只记录。
- **B2**：完整头的 payload 截断进上下文和状态、不作查询；缺头帧不产生 token/状态，会污染该 5 元组会话，直到相邻合法事件出现严格 >60 秒的空闲。检查顺序与旧代码一致（poison→倒退→头部），审计逐帧核对旧新异常身份的做法成立。
- **预检**：`run_chain` 中紧跟 `load_inputs`，在 spool、E3、训练之前。四个捕获先行，主重建按原顺序，两次摘要必须逐项相等。异常时先把帧号和空字段写入异常流再抛出，停下来也有证据。
- **Bank 前移**：`bank_metadata` 为机械抽取，`validate_banks` 在原始文件核验前执行。
- **D1**：攻击门槛读 `weighted_rate`，CIC 历史回归读 `rate`，门槛常数全部来自合同，数值为 0.99/0.97/0.97/0.1pp/1%/2%/零新增漏检/30%，与共识一致。D1 可行性：Q 基线加权 99.938%，三个 seed 均高于 99.9%，无口径冲突。
- 早期 12 条诊断只作描述；zero vector 改为阶段增量。

## 已知风险（不阻断）

`continuous_input_v2.py:206` 的 `MISSING_NAMESPACE_HEADERS`：范围内帧缺端口时整个作业停止。namespace 含端口，所以这样做是为了避免端口默认 0 伪造会话，理由成立。
但解析器按 `ip.proto` 取协议，非首片 UDP/TCP 分片正好是“有协议号、无端口”。旧 `headers_complete` 也要求端口，所以 UNSW 那 14+2 条 `INCOMPLETE_TARGET` 可能部分就是这类帧。
源 302 个捕获的旧回执 `INCOMPLETE_TARGET` 全部为 0，所以源侧不会触发，只可能在两个 UNSW 捕获的预检中触发。

不要求现在修改，理由：触发只会发生在预检（E3 之前），代价约为四个捕获的解码时间；异常流会写出帧号与空字段，足以判定类型。若触发，再按证据决定处理，例如按地址对保守污染。事先改动也无法保证不停，因为攻击流量的地址对通常正好覆盖目标。

## 上传后若预检停止

若是 `MISSING_NAMESPACE_HEADERS`、`FIXED_TARGET_INVALID` 或 `LEGACY_*_IDENTITY`，都属于输入异常，不是模型问题。请拉回 `anomaly_preflight/` 目录，双方据此出修订。
这不算科学重试，但会消耗本次一次性授权，需要用户重新授权。
