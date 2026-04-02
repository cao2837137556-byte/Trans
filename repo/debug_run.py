import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
from paths import DATA_DIR

# === 1. 直接在这里定义简单的 Transformer 检测器 ===
class SimpleTransformer(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.Tanh(), # Tanh 防止数值爆炸
            nn.Linear(32, input_dim)
        )
    def forward(self, x):
        return self.net(x)

class DebugDetector:
    def __init__(self, n_visible):
        self.model = SimpleTransformer(n_visible)
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()
        
    def process(self, x):
        # 强制归一化，防止爆炸
        x_in = np.tanh(x) 
        
        # 转 Tensor
        xt = torch.tensor(x_in, dtype=torch.float32)
        
        # 训练
        self.optimizer.zero_grad()
        out = self.model(xt)
        loss = self.criterion(out, xt)
        loss.backward()
        self.optimizer.step()
        
        return torch.sqrt(loss).item()

# === 2. 模拟 KitNET 流程 ===
print("🔍 开始诊断运行...")

# 检查数据文件
data_file = DATA_DIR / "mirai3.csv"
if not data_file.exists():
    print("❌ 错误：找不到 mirai3.csv！请确认你运行脚本的目录对不对。")
    print("当前数据目录是:", DATA_DIR)
    exit()

print("✅ 找到数据文件，开始读取...")
try:
    # 只读前 2000 行，为了快速验证
    X = pd.read_csv(data_file, header=None, nrows=2000).values
    X = np.nan_to_num(X) # 去除脏数据
    print(f"✅ 数据读取成功，形状: {X.shape}")
except Exception as e:
    print(f"❌ 读取数据失败: {e}")
    exit()

# 初始化一个简单的检测器
print("🚀 启动极简模型进行测试...")
n_features = X.shape[1]
detector = DebugDetector(n_features)
rmses = []

for i in range(len(X)):
    if i % 500 == 0:
        print(f"处理进度: {i}/{len(X)}")
    
    score = detector.process(X[i])
    
    # 修复 log(0) 问题
    if score == 0 or np.isnan(score):
        score = 1e-6
    rmses.append(score)

print("✅ 运行完成！正在画图...")

# 画图
plt.figure(figsize=(10, 4))
plt.plot(rmses)
plt.yscale('log')
plt.title("Debug Run Result")
plt.xlabel("Packet Index")
plt.ylabel("RMSE (Log Scale)")
plt.show()
print("🎉 如果你看到了图，说明环境和数据都没问题！")
