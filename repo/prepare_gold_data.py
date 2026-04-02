import pandas as pd
import numpy as np
from paths import DATA_DIR, OUTPUT_DIR

# === 配置区 ===
# 我们的目标：取前 20 万行
SLICE_SIZE = 200000
BIG_DATA_FILE = DATA_DIR / "Mirai_dataset.csv"  # 确认你的文件名是这个
BIG_LABEL_FILE = DATA_DIR / "mirai_labels.csv"
# ============

print(f"=== ✂️ 正在从完整版数据集中切取前 {SLICE_SIZE} 行 ===")

if not BIG_DATA_FILE.exists():
    print(f"❌ 还没找到 {BIG_DATA_FILE}，快去下载那个 1.37GB 的大家伙！")
    exit()

# 1. 切取特征数据
print("⏳ 正在读取大数据文件 (耐心等待，它在吃内存)...")
# 读取前 20万 行
df = pd.read_csv(BIG_DATA_FILE, header=None, nrows=SLICE_SIZE)
# 保存为我们的实验数据
output_data = OUTPUT_DIR / "my_gold_mirai.csv"
df.to_csv(output_data, header=False, index=False)
print(f"✅ 数据切片成功！保存为: {output_data}")

# 2. 切取标签数据
print("⏳ 正在对齐标签...")
df_labels = pd.read_csv(BIG_LABEL_FILE, header=None, nrows=SLICE_SIZE)
labels = df_labels.iloc[:, 0].values
output_labels = OUTPUT_DIR / "my_gold_labels.npy"
np.save(output_labels, labels)
print(f"✅ 标签切片成功！保存为: {output_labels}")

print("\n🚀 准备完毕！下一步：修改 example.py 读取 'my_gold_mirai.csv'")
