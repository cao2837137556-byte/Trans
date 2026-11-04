# Edge 冻结查询统计接口

结果：16 项合成统计检查通过；对 60,000 条真实已封存查询的身份、分母、逆纳入系数和时间块另行核验通过。
影响：本接口可以接收正式评价后保存的判定，但本轮没有读取模型分数、生成真实判定或评价外部效果。
下一步：完整 worker 用同一有序 UID 表调用本接口；正式效果仍需执行卡、独立复核和用户评价授权。

## 调用

`reporting.summarise(rows, predictions, population, prediction_uids=..., raw_name='RAW', independent_methods=('STANDARD_KNN5',), repetitions=2000, seed=20261103)`。

`rows` 是冻结的三类 `*_SELECTED_QUERIES.jsonl.gz` 所含查询元数据，按调用方固定的最终 UID 次序排列；每个方法必须提供完全相同的 `prediction_uids` 次序。每份判定是 `numpy.bool_` 的 `(N,4)` 数组，列序为 `27 / 127 / 227 / ensemble`。参考不允许进入 `rows`。HTTP 行须带已封存的整数 `tcp_flags`。

`population` 来自 `POPULATION_TEMPORAL_CENSUS.json`。交付可使用旁边确定性压缩的 `.json.gz`，解压后 SHA 必须与摘要一致。该普查从全部 4,271,308 条已封存合法候选的元数据流建立，不扫描原始 PCAP、不加载模型。原 capture/scenario 起点来自已封存执行卡；正常五个捕获段、HTTP 和 UDP 分开建块。只保留正常组件计数；攻击组件的纳入概率未知，不把数百万伪造五元组当作可估计的独立攻击组件。

## 三类统计与门

- 选中样本比率是整数报警数除选中查询数。正常列 FP，攻击列 FN，并分列四头、三类角色、捕获段与协议。
- 正常组件等权使用封存的 `component_metric_weight`；既有 device/capture-or-scenario/component 层次权重另外列出，避免混淆。
- 人口估计是逆纳入系数加权的报警数除已知完整合法人口 N。不得改为除扩张后的样本数，不归一化、不截断到 `[0,1]`。未抽中一律 `NOT_SAMPLED`；整组无选中时不输出零误报估计。
- HTTP 互斥层和重叠 `SYN_NO_ACK / ACK_NO_SYN / ACK_ONLY / PSH_ACK / OUTSIDE_SYN_GUARD` 分开报告，UDP 单列。GET/载荷字段不在冻结元数据中，明确 `NOT_EVALUABLE`；PSH 不能代替它们。
- C5/p1 必须是 RAW 判定的子集；独立 kNN-5 允许增加 RAW 阴性上的报警。源累计撤警按设备 ≤1pp、观察到的 scenario ≤5pp；RAW 加权召回低于 99% 的组必须零撤警。scenario 不是独立攻击事件；无官方事件账本的事件门明确不可评价。
- 正常只抽了 post-7200 查询，正常 FULL FPR 为 `NOT_EVALUABLE_POSTWINDOW_ONLY_SELECTION`。攻击 FULL/primary 复用同一合法攻击人口，不重复算作独立证据。

## 时间敏感性

每个原 capture/scenario 用整数纳秒和原始锚点建立 60 秒连续块，从第一至最后合法候选块，保留中间零合法人口块及零选中块。各组内部抽取同样数量的块，共 2,000 次，固定 seed `20261103`；每块 HT 报警分子和精确合法人口分母共同重采样，给出 2.5/97.5 分位数。点估计仍除固定全 N。

这是给定冻结查询样本的条件时间敏感性区间，不证明完整抽样设计的 95% 覆盖，不把包或伪造源地址当独立攻击，不保证 ±0.3pp。HTTP 只有 5 块、UDP 只有 7 块，这一局限必须随结果保留。

回执单列 `positive_denominator_repetitions` 和 `zero_denominator_repetitions`，两者合计等于重采样次数。`valid_repetitions` 仅计有选中样本且分母为正的可报告重复；整组未抽中时该值为 0、区间为空，但仍保留实际零/正分母次数，避免把人口存在误作已有可评价预测。

## 核验

`python test_reporting.py` 写 `STATISTICS_TEST_RECEIPT.json`：16 项合成检查覆盖三种比率互不相同、四头列序、HT 不截断、已知 N 分母、原始时钟/整数边界、空块/未抽中块、场景不混合、UID 错配、参考误入分母、低 RAW 召回门、独立 kNN 和缺失组。

`python build_population_census.py` 只读全部已封存元数据并核对输入前后 SHA；生成 census、gzip、旁路哈希和 `POPULATION_TEMPORAL_CENSUS_SUMMARY.json`。

`python verify_reporting_metadata.py` 不读判定，仅核验实际 60,000 查询：三角色扩张人口精确为 `1,220,126 / 152,352 / 2,898,830`；正常 17,025 组件等权、总质量 1；4,124 参考 UID 与查询零重叠。回执为 `STATISTICS_METADATA_VERIFICATION.json`。
