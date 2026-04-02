import numpy as np
from paths import OUTPUT_DIR

print("=== 🔍 波峰数值大比拼 ===")

try:
    # 读取你跑出来的 RMSE 结果
    rmses = np.load(OUTPUT_DIR / "rmse_gold.npy")
    print(f"✅ 成功加载结果，总长度: {len(rmses)}")
except:
    print("❌ 找不到 rmse_gold.npy，请先运行 example.py")
    exit()

# 1. 定义两个区间
# 区间 A: 71,000 附近的“可疑波峰” (正常)
start_A, end_A = 70000, 75000
# 区间 B: 121,621 之后的“攻击高峰” (异常)
start_B, end_B = 121621, 130000

# 2. 找出这两个区间的最大值
max_A = np.max(rmses[start_A:end_A])
mean_A = np.mean(rmses[start_A:end_A])

max_B = np.max(rmses[start_B:end_B])
mean_B = np.mean(rmses[start_B:end_B])

print(f"\n🏔️  [正常高流量区] (70k ~ 75k)")
print(f"    - 最高分 (Max RMSE): {max_A:.4f}")
print(f"    - 平均分 (Mean RMSE): {mean_A:.4f}")

print(f"\n🌋  [真实攻击爆发区] (121k+)")
print(f"    - 最高分 (Max RMSE): {max_B:.4f}")
print(f"    - 平均分 (Mean RMSE): {mean_B:.4f}")

# 3. 最终判决
ratio = max_B / max_A if max_A > 0 else 0
print(f"\n⚖️  差距倍数 (攻击 / 正常): {ratio:.2f} 倍")

if ratio > 5.0:
    print("✅ 结论：这是'视觉欺骗'。攻击分数远高于正常波峰，模型分得很清楚！")
elif ratio > 1.5:
    print("⚠️ 结论：有点危险。虽然攻击更高，但正常波峰也很高，可能会有误报。")
else:
    print("❌ 结论：实锤了。模型确实分不清这两个波峰，需要增加训练数据或调整参数。")
