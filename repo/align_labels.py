import pandas as pd
import numpy as np
from paths import DATA_DIR, OUTPUT_DIR

print("=== 正在启动标签对齐程序 ===")

# 1. 自动寻找 csv 文件
# 防止因为 Windows 隐藏后缀名导致找不到文件
possible_names = ["mirai_labels.csv", "mirai_labels"]
filename = None

for name in possible_names:
    candidate = DATA_DIR / name
    if candidate.exists():
        filename = candidate
        break

if filename is None:
    print("❌ 找不到 mirai_labels 文件！请确认它就在 example.py 旁边。")
    exit()

print(f"✅ 找到标签文件: {filename}")

# 2. 读取你的 RMSE 结果长度 (为了知道要剪多少)
try:
    my_results = np.load(OUTPUT_DIR / "rmse_results.npy")
    target_len = len(my_results)
    print(f"✅ 你的数据集 (mirai3) 长度: {target_len}")
except:
    # 如果没找到结果文件，默认按你之前的截图设为 100,000
    target_len = 100000
    print(f"⚠️ 没找到 rmse_results.npy，默认假设你需要: {target_len} 行")

# 3. 读取并裁剪官方标签
print("⏳ 正在读取官方标签 (这可能需要几秒钟)...")
try:
    # 官方标签没有表头，第一行就是数据
    df = pd.read_csv(filename, header=None)
    full_labels = df.iloc[:, 0].values # 取第一列
    
    print(f"✅ 官方标签总长度: {len(full_labels)} (是不是 76万多？)")

    if len(full_labels) >= target_len:
        print(f"✂️ 正在裁剪前 {target_len} 行...")
        
        # === 核心步骤：只取前 100,000 个 ===
        aligned_labels = full_labels[:target_len]
        
        # 统计一下里面有多少攻击
        attacks = np.sum(aligned_labels)
        print(f"📊 你的数据集中包含:")
        print(f"   - 正常样本: {target_len - attacks}")
        print(f"   - 攻击样本: {attacks}")
        
        # 4. 保存为标准答案
        np.save(OUTPUT_DIR / "official_labels.npy", aligned_labels)
        print("\n🎉 成功！已生成 'official_labels.npy'。")
        print("👉 现在你可以运行 evaluate_auc.py 算出最终的官方分数了！")
        
    else:
        print(f"❌ 奇怪，官方标签只有 {len(full_labels)} 行，不够你的 {target_len} 行？")

except Exception as e:
    print(f"❌ 读取出错: {e}")
