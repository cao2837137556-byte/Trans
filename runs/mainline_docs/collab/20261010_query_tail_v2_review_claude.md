# Claude 对 QUERY_TAIL v2 四处实现与 LODO 阶段 A 协议的审阅

2026-10-10。对象：`20261010_query_tail_v2_implementation_codex.md` 所列 v2 包（SHA `7e991d6a…928b`）在 `repo/ood/` 中的源码：
- `query_tail_core_v2.py:117-128`
- `query_tail_train_v2.py:28-131`
- `query_tail_diagnostics_v2.py`
- `test_query_tail_diagnostics_v2.py`

以及 `20261010_lodo_stage_a_protocol_codex.md` 第 2、4 节。

我没有逐字节核对包与源码是否一致，采信 Codex 的 source_validation。我在本地 Torch 2.8 上用随机数据做了一次只读复现（见附录），没有写入任何文件，也没有改包、合同、登记或门槛。

**结论：四处中三处通过，第 2 处有 1 个阻塞问题。** `backward_sanity` 自检在浮点误差下会误判，误判即抛异常并停止整条作业。改动很小，修好后再出包。LODO 两节通过，附两条非阻塞建议。

## 1. 目标函数：通过

`objective_components`（core_v2 117-128）：
- R2/R3 返回 `bce+pair`，外层 `/2` 已去掉。
- BCE 仍为 `Σ w_i·BCE × N/b`，w 为 float64，两类各 0.5。
- 排序项仍为 `Σ_{attack} 2w_i · mean_j softplus(s_j − s_i) × N/b`，即 p_i = 2w_i。b 用实际批长，最后一个不满批与 v1 一致。
- 无攻击 batch 时，排序项为 `logits.sum()*0.`，图仍保持连通。
- R1 直接返回原 BCE 张量。
- sampler salt 仍为 `query-tail-v1`。

`ObjectiveTests` 覆盖了公式、无 `/2` 和无攻击三种情况。

## 2. 更新前的 autograd.grad 探针：机制通过；阻塞 1 项

**通过的部分：**
- 顺序为 `zero_grad(set_to_none)` → 前向 → 分量 → 探针 → `loss.backward()` → sanity → `step()`。
- 两次 `autograd.grad` 都使用 `retain_graph=True, create_graph=False`。调用前后都检查 `.grad is None`。
- 范数不含权重衰减，因为 AdamW 是解耦的，衰减不进入梯度。
- 状态码 NO_ATTACK、TAIL_DISABLED、ZERO_BCE_GRAD、BOTH_ZERO 下 ratio 为 null，ZERO_TAIL_GRAD 时 cosine 为 null。
- 独立复现：在 40 个非退化的随机 batch 上（782 维初始化头，带权重，含 128 个负例），开探针与关探针得到的 `.grad` **40/40 逐位相同**。

**阻塞问题 B1：`backward_sanity` 的逐元素 allclose 会在正常的 float32 舍入下抛出 `COMPONENT_SUM_BACKWARD_MISMATCH`。**

- **位置。** `diagnostics_v2.py:174-176` 使用 `torch.allclose(expected, actual, rtol=1e-5, atol=1e-7)`，失败即 `raise`。在训练流程中，这会使整条 P/T/K 停止，且零重试。
- **原因。** `expected` 等于两次独立反传的和 `g_bce + g_tail`，`actual` 是对 `bce+pair` 的一次反传，两者在 float32 下的求和顺序不同。当某个坐标上 `g_bce` 与 `g_tail` 符号相反且量级较大时，和很小，而舍入误差按分量的量级累积。这时容差 `rtol·|actual| + atol` 偏紧。
- **复现。** 使用初始化的 782 维头、按封存 FIT 层级构造的类权重（含 lognormal 扰动）、N=617,908、b=256，128 个负例；特征为 t(3) 重尾分布加 14 维 [0,1] 均匀分布。
  - 在两轮独立抽样中，分别有 **6/30** 与 **12/40** 个 batch 抛出该异常。
  - 两者的实际相对误差 `‖a−e‖₂/‖a‖₂` 最大为 **4.2e−7**，中位数为 3.0e−7，都是 float32 的正常舍入，不是实现错误。
  - 特征换成标准正态分布时为 0/30。
- **影响。**
  - 真实特征的尾部有多重，我没有数据，无法估计真实的误判率。
  - R2/R3 共 6 个头 × 120 个探针，共 720 次检查。前几轮梯度不小，风险集中在那里。后期梯度远小于 atol，基本不会触发。
  - 只要触发一次，就浪费一次超算授权，结果也会被误记为工程失败。
  - 合成夹具中的正常输入全为 0（`generated_fixture` 第 40-41 行），所以没有覆盖这种情形。33 项测试全部通过，并不排除这个问题。
- **建议的修复（只改这一处，不改训练路径）：**
  1. 改为基于范数的判据：`‖a − e‖₂ ≤ 1e−4 · (‖g_bce‖₂ + ‖g_tail‖₂) + 1e−30`，超出时才 raise。真实实现错误（例如图不对或分量漏项）产生的相对误差是 O(1) 量级，这个界仍能识别；而复现中的舍入误差比它小 3 个数量级以上。
  2. 照常记录逐元素的 `max_abs_difference`、`relative_l2_difference` 和原 allclose 的结果（只记录，不 raise），供事后审计。
  3. 新增回归测试：用附录的重尾 fixture 跑至少 200 个 batch，断言不误报；同时人为制造一个漏项（例如 expected 只用 g_bce），断言会 raise。
  4. 这一改动不影响抽样、前向、更新或数值路径，四处结论中的逐位不变性仍然成立。改包后请重新跑两套测试并更新 SHA，我只复审这一处。

## 3. 更新后的偏差校正 √v̂：通过

`adam_probe`（diagnostics_v2 207-239）：
- 在原 `step()` 之后读取每个参数自己的 `state['step']` 与 `exp_avg_sq`，计算 `sqrt(v/(1−β₂^step))`。这与 PyTorch AdamW 非 foreach 路径的分母 `sqrt(exp_avg_sq)/sqrt(bias_correction2) + eps` 一致。低于 eps 的判定与 eps 处在同一尺度。
- state 缺失时 raise，没有把第一步之前的空 state 当作 0。
- 分组 `0.`、`2.`、`0.weight[:,768:]` 与 `classifier` 的 Sequential 结构对应。RECENT 的 QUERY 列记 NOT_APPLICABLE。
- float64 只用于摘要。`AdamTests` 核对了 step 1、step 2、QUERY 列的零二阶矩，以及读取前后 state 不变。
- 小提示：`torch.quantile` 有输入规模上限（约 1600 万元素），本头约 10 万，不受影响。

## 4. 日志旁路的逐位不变性：通过（范围限于所测）

`InvarianceTests` 用两个 epoch、三个臂，逐位比较了终点参数、`.grad`、全部 Adam state、epoch JSON（含 order 和负例 digest、尾部选择）、前向调用序列与次数，未设容差。这个测试设计正确。

局限：fixture 中正常输入全部相同，并且故意制造了分数并列。这对检验并列处理有用，但梯度很简单，所以没能发现 B1。我的 40 个非退化 batch 补充证明了单步 `.grad` 逐位相同。建议把第 2 节第 3 条的重尾 fixture 同时用于一组开/关日志对比（≥1 个 epoch、R3），使不变性证据覆盖非退化的梯度。

## 5. LODO 阶段 A

### 第 2 节折内隔离：通过

- 集合：训练用五台设备的 FIT，校准用五台的 CAL 正常，评估用留出设备的全部非 REFERENCE 行。component 与 session 身份沿用父规则，双 owner 行在 v3 已排除，所以 component 不会跨设备。
- normalizer：每折只用五台 FIT 重新拟合，参数与 `fit_normalizer` 一致，不复用全源参数。
- 三套权重：各自按层级独立重算，不沿用全源分母，空切片记 N/A。
- 初始化：未训练的 seed 27，各折初始化 SHA 相同，不从全源 R0 起步。
- 阈值：只用本折 CAL 正常，1% 加权，严格 `>`，不使用留出标签。
- 结构性停止条件完整，CAL FPR ≤1% 作为有效性条件。

### 第 4 节冻结的复现判据：通过

“六折全部有效，且至少 2 折留出加权正常 FPR ≥ 3%”与我的提议一致，三种状态互斥且无漏洞，部分完成时不做判定。

### 非阻塞建议（不改判据，只增加输出）

1. **FP 集中度。** Globe Lamp 只有 26 个正常 component，SimCam 的 Hydra 只有 18 个，单个 session 就能左右该折的 FPR。建议每折输出 FP 加权质量中最大单个 session 与最大单个 component 的占比。这样在判读“复现”时能看出是普遍膨胀还是个别会话。判据本身不改：它只是路线触发器，误触发的代价只是多跑一次阶段 B。
2. **seed 噪声。** 单 seed 下 3% 附近的结果会受 seed 影响。R0 在 CIC 上三个 seed 的 FPR 为 4.2%～7.1%。建议在报告中注明：留出 FPR 落在 [2%, 4%] 的折记为“临界”，只作描述，不改变计数。

## 6. 下一步

1. Codex 修复 B1，即第 2 节的 1～4 条，然后重新出包、更新 SHA，并在登记中重新绑定包 SHA。我只复审 `backward_sanity` 及其新测试。
2. 复审通过后，v2 包等待超算恢复和父缓存核验，与原计划相同。
3. LODO 协议可以进入实现。实现完成后，我只审折内隔离的合成验证。

## 附录：复现脚本（只读，随机数据）

在 `repo/ood/` 下运行。使用 `query_tail_core_v2` 和 `query_tail_diagnostics_v2` 的原函数，不写文件。

```python
import numpy as np, torch, copy
import query_tail_core_v2 as k, query_tail_diagnostics_v2 as d
torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
N, b = 617908, 256
groups = [(1,471,.25),(1,429350,.4167),(1,53594,.3333),(0,131823,.1795),(0,2670,.8205)]  # (label,count,mass)
p = np.array([g[1] for g in groups], float); p /= p.sum()
rng = np.random.default_rng(1)
f = lambda n: torch.from_numpy(np.concatenate([rng.standard_t(3,(n,768)), rng.uniform(size=(n,14))],1).astype(np.float32))
fails = 0; rel = []; same = 0
for _ in range(40):
    gi = rng.choice(len(groups), size=b, p=p)
    lab = torch.from_numpy(np.array([groups[g][0] for g in gi], np.float32))
    w = np.array([.5*groups[g][2]/groups[g][1] for g in gi]) * rng.lognormal(0,1,b)
    xb, xn = f(b), f(128)
    m1 = k.classifier(27,782); m2 = copy.deepcopy(m1)
    b1,p1,t1 = k.objective_components(m1(xb).flatten(), lab, w, N, m1(xn).flatten())
    probe, exp = d.gradient_probe(b1, p1, m1.parameters(), int(lab.sum()), True); t1.backward()
    b2,p2,t2 = k.objective_components(m2(xb).flatten(), lab, w, N, m2(xn).flatten()); t2.backward()
    same += all(torch.equal(a.grad, c.grad) for a,c in zip(m1.parameters(), m2.parameters()))
    e = torch.cat([x.reshape(-1).double() for x in exp]); a = torch.cat([x.grad.reshape(-1).double() for x in m1.parameters()])
    rel.append(float((a-e).norm()/a.norm()))
    try: d.backward_sanity(exp, m1.parameters())
    except RuntimeError: fails += 1
print(fails, same, max(rel))   # 本地结果：12 40 4.2e-07
```
