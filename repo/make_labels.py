import numpy as np
import pandas as pd
from paths import OUTPUT_DIR

# 1. 设定总包数 (根据你的 rmse_results.npy 长度)
# 你截图里显示是 100000
total_packets = 100000

# 2. 创建全 0 数组 (假设全是正常)
labels = np.zeros(total_packets, dtype=int)

# 3. 【关键】根据图表，手动标记攻击区间
# 从你的图来看，大约第 75,000 个包开始，RMSE 突然变大且剧烈波动
attack_start = 75000 
labels[attack_start:] = 1  # 75000 以后标记为攻击 (1)

print(f"生成的标签统计:")
print(f"  - 总数: {len(labels)}")
print(f"  - 正常样本 (0): {np.sum(labels == 0)}")
print(f"  - 攻击样本 (1): {np.sum(labels == 1)}")
print(f"  - 攻击开始位置: {attack_start}")

# 4. 保存为文件
output_labels = OUTPUT_DIR / "my_labels.npy"
np.save(output_labels, labels)
print(f"✅ 成功生成临时标签文件: {output_labels}")
