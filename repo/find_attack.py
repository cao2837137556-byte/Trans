import pandas as pd
import numpy as np
from paths import DATA_DIR

print("正在扫描官方标签文件，寻找攻击起始点...")

# 读取官方标签
try:
    df = pd.read_csv(DATA_DIR / "mirai_labels.csv", header=None)
    labels = df.iloc[:, 0].values
    
    # 找所有是 1 的位置
    attack_indices = np.where(labels == 1)[0]
    
    if len(attack_indices) > 0:
        first_attack = attack_indices[0]
        last_attack = attack_indices[-1]
        print(f"✅ 找到了！官方数据集中：")
        print(f"   - 第一次攻击出现在第 {first_attack} 行")
        print(f"   - 最后一次攻击出现在第 {last_attack} 行")
        print(f"   - 攻击总行数: {len(attack_indices)}")
        
        # 帮你做个推算
        # 你的 mirai3.csv 里攻击出现在约 75,000 行
        # 如果 mirai3 是从官方数据里截取的，那它可能的起点是：
        estimated_start = first_attack - 75000
        print(f"\n🕵️‍♂️ 推理分析：")
        print(f"   如果你的 mirai3.csv 里的攻击就是官方的第一次攻击...")
        print(f"   那么 mirai3.csv 可能是从官方数据的第 [{estimated_start}] 行开始截取的！")
        
    else:
        print("❌ 奇怪，官方标签里竟然完全没有 1？(请检查 Excel 里的 1 是不是被当成字符了)")

except Exception as e:
    print(f"❌ 出错: {e}")
