import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from paths import DATA_DIR, OUTPUT_DIR

print("=== 🚀 开始执行原始数据指纹对齐 ===")

# 1. 寻找原始数据的突变点 (Physical Shockwave)
print("1️⃣  正在分析 mirai3.csv 原始特征分布...")
# 读取原始数据
X = pd.read_csv(DATA_DIR / "mirai3.csv", header=None).values

# 计算每一行的“能量” (L1 范数：所有特征绝对值之和)
# 这代表了流量的猛烈程度，完全不依赖 AI 模型
magnitudes = np.sum(np.abs(X), axis=1)

# 计算变化率 (差分)，找到变化最剧烈的那一瞬间
diffs = np.diff(magnitudes)
# 突变点 = 变化率最大的位置
my_shock_point = np.argmax(np.abs(diffs))

print(f"    📊 原始数据指纹显示：在第 [{my_shock_point}] 行发生了最大规模的流量突变。")
print("       (我们将以此作为攻击爆发的物理锚点)")

# 2. 寻找官方标签的起点
print("\n2️⃣  正在读取官方标签 mirai_labels.csv ...")
if not (DATA_DIR / "mirai_labels.csv").exists():
    print("❌ 找不到 mirai_labels.csv，请检查文件位置！")
    exit()

# 这种读取方式比较快
df_labels = pd.read_csv(DATA_DIR / "mirai_labels.csv", header=None)
full_labels = df_labels.iloc[:, 0].values

# 找到第一个为 1 的位置
official_attack_starts = np.where(full_labels == 1)[0]
if len(official_attack_starts) == 0:
    print("❌ 官方标签里没有攻击？请检查文件。")
    exit()

official_shock_point = official_attack_starts[0]
print(f"    📋 官方标签记录：第一次攻击开始于第 [{official_shock_point}] 行。")

# 3. 计算偏移量 (Offset)
# 逻辑：官方的第 121621 行 = 我的第 75000 行 (举例)
# 所以偏移量 = 121621 - 75000
offset = official_shock_point - my_shock_point
print(f"\n3️⃣  📐 计算出的时间轴偏移量: {offset}")
print(f"       这意味着 mirai3.csv 是从官方数据的第 {offset} 行开始截取的。")

# 4. 生成对齐的标签
print("\n4️⃣  正在生成最终标签...")
target_len = len(X) # 我的数据长度
start_idx = offset
end_idx = offset + target_len

# 边界检查
if start_idx < 0:
    print("⚠️ 警告：偏移量为负？说明你的数据里包含的攻击比官方记录的还早？这不太可能，除非数据源不同。")
    # 强制修正：假设从 0 开始
    start_idx = 0
    end_idx = target_len

if end_idx > len(full_labels):
    print("⚠️ 警告：截取长度超过了官方标签总长，末尾填充 0 处理。")
    # 截取能截取的
    aligned_labels = full_labels[start_idx:]
    # 补 0
    pad_len = target_len - len(aligned_labels)
    aligned_labels = np.concatenate([aligned_labels, np.zeros(pad_len)])
else:
    # 正常截取
    aligned_labels = full_labels[start_idx : end_idx]

# 5. 保存
np.save(OUTPUT_DIR / "official_labels.npy", aligned_labels)

print("\n" + "="*40)
print(f"✅ 成功生成 'official_labels.npy'")
print(f"   - 标签长度: {len(aligned_labels)}")
print(f"   - 攻击样本数: {np.sum(aligned_labels)}")
print("="*40)
print("👉 现在，这是基于【数据物理特征】而非【模型预测】得出的标签。")
print("👉 请立即运行 evaluate_auc.py 查看最终结论！")

# 6. 画个图验证一下 (可选)
plt.figure(figsize=(10,6))
# 画原始数据能量（归一化方便显示）
plt.plot(magnitudes/np.max(magnitudes), label='Raw Data Energy (mirai3.csv)', alpha=0.7)
# 画对齐后的标签
plt.plot(aligned_labels, label='Aligned Labels', color='red', alpha=0.5, linestyle='--')
plt.title("Verification: Do the Raw Data and Labels Align?")
plt.legend()
plt.show()
