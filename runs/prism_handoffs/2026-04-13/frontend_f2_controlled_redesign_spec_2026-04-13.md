# Frontend-F2 受控重构设计书

日期：2026-04-13  
状态：设计冻结，待按此实现  
目标：在不破坏现有 `original-frontend 100D` 主线的前提下，把 Kitsune 原始前端抽取阶段升级为“同时输出 flat 缓存 + 结构化缓存”的双轨版本，为后续 Transformer-native frontend 实验提供受控输入。

---

## 1. 设计结论

当前最合理的方向不是引入外部黑盒前端，而是**沿用 Kitsune 的原始统计逻辑，只改缓存表达形式**。

原因有三条：

1. 论文主线必须可辩护  
   当前 strongest paper candidate 建立在 `original-frontend 100D + stronger OOD` 上。直接接第三方前端，会把“模型问题”和“前端替换问题”搅在一起。

2. 我们已经排除了“同一 100D 再组织就能翻盘”的幻想  
   `timescale_tokenizer` 和 `structured_frontend_v1` 已经证明：同源 100D 重新排成 token 有机制信号，但不足以进入主线竞争区。

3. 真突破口在 upstream expression  
   现在的 100D 是在抽取阶段就被拼平成扁平向量的。Transformer 需要的时空与语义结构，已经在缓存落盘前被压掉了。

因此，`Frontend-F2` 的核心不是“换统计量”，而是：

> 保持 Kitsune 的统计过程不动，把输出缓存从“只有 flat 100D”升级为“flat 100D + 结构化语义缓存 + 元数据映射”。

---

## 2. 现有 100D 是怎么来的

原始前端的关键代码在：

- [FeatureExtractor.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/kitsune_frontend_original/FeatureExtractor.py)
- [netStat.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/kitsune_frontend_original/netStat.py)
- [kitsune_frontend_original_extract.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/kitsune_frontend_original_extract.py)

真实结构不是“100 个互相独立的数”，而是：

- `MI_dir`: 15 维 = `5 scales x 3 stats`
- `HH`: 35 维 = `5 scales x 7 stats`
- `HH_jit`: 15 维 = `5 scales x 3 stats`
- `HpHp`: 35 维 = `5 scales x 7 stats`

总计：

- `15 + 35 + 15 + 35 = 100`

五个时间尺度来自 `netStat.py:43-48`：

- `5`
- `3`
- `1`
- `0.1`
- `0.01`

因此，当前 100D 其实天然带有：

- family 结构
- scale 结构
- stat-type 结构

只是这些结构在落盘时被直接拼平了。

---

## 3. F2 的原则

### 保留什么

- 保留原始 Kitsune 增量统计逻辑
- 保留 flat 100D 输出
- 保留现有 stronger OOD 数据协议与切分逻辑

### 改什么

- 只改 `kitsune_frontend_original_extract.py` 的缓存输出层
- 增加结构化缓存与语义元数据

### 不做什么

- 第一轮不改 `FeatureExtractor.py` 的 packet parsing
- 第一轮不改 `netStat.py` 的统计公式
- 第一轮不引入新的 feature family
- 第一轮不接外部 GitHub 黑盒实现

---

## 4. 需要修改的文件与具体位置

主文件：

- [kitsune_frontend_original_extract.py](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/kitsune_frontend_original_extract.py)

### 改造点 A：在 imports 后增加结构化 schema helper

当前位置参考：

- `kitsune_frontend_original_extract.py:12-19`

在这里之后新增 helper 函数：

1. `parse_feature_header(header: str) -> dict`
2. `build_feature_schema(headers: list[str]) -> dict`
3. `build_structured_feature_views(arr: np.ndarray, schema: dict) -> dict`
4. `save_structured_cache(run_dir: Path, views: dict, schema: dict) -> dict`

目的：

- 把 `feature_headers.txt` 对应的 100 个 flat 维度解析成 family/scale/stat-slot 结构
- 直接在抽取脚本里同步产出结构化缓存

### 改造点 B：保持 `extract_features_from_tsv` 只负责拉平向量

当前函数位置：

- `kitsune_frontend_original_extract.py:148-182`

当前行为：

- 只返回 `arr, headers, counters`

F2 第一轮建议：

- 保持函数签名不变
- 不在这里直接做结构化拼装
- 仍然只负责“从原始 FE 拉出 flat 向量与 header”

原因：

- 抽取逻辑与缓存逻辑分离更稳
- 便于验证 flat 100D 是否与历史完全一致

### 改造点 C：在 main 中新增结构化缓存生成与保存

当前关键位置：

- `kitsune_frontend_original_extract.py:213-218`

现在这里做的是：

- 保存 `feature_path = *.npy`
- 保存 `feature_headers.txt`

F2 要在这里后面追加：

1. 解析 schema
2. 生成 structured views
3. 保存 `.npz` 结构化缓存
4. 保存 `structured_schema.json`
5. 在 metadata 与 summary 中登记这些新文件

### 改造点 D：增加 CLI 开关

当前参数位置：

- `kitsune_frontend_original_extract.py:187-191`

建议新增：

- `--emit-structured-cache`，默认开启
- `--structured-format {npz}`，第一轮只支持 `npz`

第一轮不建议搞多个格式，避免接口发散。

---

## 5. 新的结构化缓存应该长什么样

F2 第一轮不要发明复杂对象。最稳的是：

### 文件 1：保留旧文件

- `*_features_firstXXXXX.npy`

含义：

- 原始 flat 100D
- shape: `[N, 100]`

作用：

- 向后兼容
- 保证历史主线完全不受影响

### 文件 2：新增结构化缓存

- `*_features_firstXXXXX_structured.npz`

建议内部字段如下：

#### `flat_features`

- shape: `[N, 100]`
- dtype: `float32`

说明：

- 直接把 flat 100D 再存一份到结构化包里，方便单文件加载

#### `family_scale_tokens`

- shape: `[N, 4, 5, 7]`
- dtype: `float32`

含义：

- 第 1 维：family
- 第 2 维：scale
- 第 3 维：stat slot

固定 family 顺序：

1. `MI_dir`
2. `HH`
3. `HH_jit`
4. `HpHp`

固定 scale 顺序：

1. `5`
2. `3`
3. `1`
4. `0.1`
5. `0.01`

固定 stat-slot 顺序：

1. `weight`
2. `mean`
3. `std`
4. `radius`
5. `magnitude`
6. `covariance`
7. `pcc`

其中：

- `MI_dir` 只填前 3 个 slot，后 4 个补 0
- `HH_jit` 只填前 3 个 slot，后 4 个补 0
- `HH` 与 `HpHp` 填满 7 个 slot

这是 F2 第一轮最重要的结构化表达。

#### `token_matrix`

- shape: `[N, 20, 7]`
- dtype: `float32`

含义：

- 把 `[4, 5, 7]` 拉平成 `20 semantic tokens x 7 stat slots`

token 顺序建议固定为：

- family-major，再按 scale 排序

即：

1. `MI_dir@5`
2. `MI_dir@3`
3. `MI_dir@1`
4. `MI_dir@0.1`
5. `MI_dir@0.01`
6. `HH@5`
7. `HH@3`
8. `HH@1`
9. `HH@0.1`
10. `HH@0.01`
11. `HH_jit@5`
12. `HH_jit@3`
13. `HH_jit@1`
14. `HH_jit@0.1`
15. `HH_jit@0.01`
16. `HpHp@5`
17. `HpHp@3`
18. `HpHp@1`
19. `HpHp@0.1`
20. `HpHp@0.01`

这个视图是给 Transformer-native frontend 直接喂 token 的。

#### `token_slot_mask`

- shape: `[20, 7]`
- dtype: `float32`

含义：

- 标记哪些 stat-slot 真实存在
- 对 `MI_dir` 和 `HH_jit`，后四位为 0

作用：

- 后续模型可据此做 masked pooling / masked projection

#### `token_family_id`

- shape: `[20]`
- 值域：`0..3`

#### `token_scale_id`

- shape: `[20]`
- 值域：`0..4`

作用：

- 直接作为 family embedding / scale embedding 的索引

### 文件 3：新增 schema 元数据

- `*_features_firstXXXXX_structured_schema.json`

内容至少包含：

- family 列表
- scale 列表
- stat-slot 列表
- 100 个 flat header 对应到哪个 `(family, scale, stat-slot)`
- 哪些 slot 是 padded
- token 展开顺序

这是后续所有 F2/F3 模型的固定协议文件。

---

## 6. 为什么不用外部 GitHub 前端当第一版

第一版如果直接引第三方前端，会有四个问题：

1. 无法控制变量  
   你分不清性能变化来自“前端表达”还是“别人偷偷做了别的工程优化”。

2. 不利于论文叙事  
   论文现在最强的故事线是：我们沿着 Kitsune 的可信输入链，一步步发现并修复 stronger OOD 下的结构问题。直接换前端，会把这条证据链打断。

3. 不利于失败归因  
   第一轮 F2 若失败，我们需要知道到底是“结构化缓存思路不对”，还是“外部实现混入了别的问题”。

4. 工程风险更高  
   第三方代码的数据清洗、协议字段、时间窗口定义很可能跟现在的 stronger OOD 主线不兼容。

结论：

> 外部 GitHub 前端可以作为灵感来源或后续扩展对照，但不应该成为 F2 第一版主实现。

---

## 7. F2 第一轮 smoke 的最小范围

不要一上来就开超算大跑。先做一个受控 smoke：

### 第一步：实现结构化缓存输出

输入：

- 与当前 `kitsune_frontend_original_extract.py` 相同的 pcap / tsv

输出：

- flat 100D
- structured `.npz`
- schema `.json`

验收条件：

- `flat_features` 与历史 `*_features_firstXXXXX.npy` 数值逐元素一致
- `family_scale_tokens` 可逆恢复到 flat 100D
- schema 映射和 `feature_headers.txt` 完全一致

### 第二步：做最小读取自检

写一个小脚本或 notebook 检查：

- `token_matrix.shape == [N, 20, 7]`
- `token_slot_mask` 是否正确屏蔽 padded 位
- family/scale id 是否与预期顺序一致

### 第三步：再决定模型实验

只有在结构化缓存完全自洽后，才进入 `frontend_f2_structured_tokenizer_v1`。

---

## 8. F2 后续训练线应该怎么接

F2 第一轮做完后，建议的下一条训练线是：

### `frontend_f2_structured_tokenizer_v1`

输入：

- `token_matrix [N, 20, 7]`
- `token_slot_mask [20, 7]`
- `token_family_id [20]`
- `token_scale_id [20]`

模型最小版本：

1. 对每个 token 的 7 维 stat-slot 做线性投影
2. 加 family embedding
3. 加 scale embedding
4. 送入浅层 Transformer encoder
5. 输出 token-wise reconstruction 或 latent score

注意：

- 第一轮 scorer 仍沿用当前已验证过有信号的 `z_short_mean_minus_long_mean_a1.50`
- 控制变量，不要同时换 scorer 家族

---

## 9. 执行顺序

建议严格按下面顺序来：

1. 修改 `kitsune_frontend_original_extract.py`
2. 生成 flat + structured 双缓存
3. 做可逆性 / 一致性 smoke
4. 写 `prepare_frontend_f2_sources.py`，只消费新结构化缓存
5. 再开 `frontend_f2_structured_tokenizer_v1`

不要反过来。

---

## 10. 当前结论

当前最合理的判断是：

- 不是“继续在同一 100D 上调后端”
- 也不是“立刻接外部黑盒前端”
- 而是：

> **基于 Kitsune 原始提取逻辑，做受控的 upstream frontend expression 重构。**

F2 第一轮的任务非常具体：

> **把原来只会吐 flat 100D 的抽取脚本，升级成会同时吐出结构化语义缓存的双轨脚本。**

这一步如果做稳，后面才真正有资格谈“Transformer-native frontend”。
