import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, roc_curve
from paths import OUTPUT_DIR

print("=== 🏆 最终验证：基于官方对齐标签 ===")

# 1. 加载预测结果
try:
    y_scores = np.load(OUTPUT_DIR / "rmse_results.npy")
    print(f"✅ 成功加载预测结果 (RMSE), 长度: {len(y_scores)}")
except:
    print("❌ 找不到 rmse_results.npy")
    exit()

# 2. 加载你刚刚生成的官方对齐标签
# 👇👇👇 重点是改了这里 👇👇👇
try:
    y_true = np.load(OUTPUT_DIR / "official_labels.npy")
    print(f"✅ 成功加载官方对齐标签 (Official Labels), 长度: {len(y_true)}")
except:
    print("❌ 找不到 official_labels.npy！请确保你刚刚运行了 auto_align.py")
    exit()

# 3. 长度对齐 (以防万一有一两行的误差)
min_len = min(len(y_scores), len(y_true))
y_scores = y_scores[:min_len]
y_true = y_true[:min_len]

# 4. 剔除预热期 (前 15000 个)
# 预热期模型强制输出 0 或 1e-6，不具备参考价值，必须剔除
warmup = 15000
if min_len > warmup:
    print(f"✂️ 剔除前 {warmup} 个预热样本，只评估正式运行阶段...")
    y_scores_eval = y_scores[warmup:]
    y_true_eval = y_true[warmup:]
else:
    y_scores_eval = y_scores
    y_true_eval = y_true

# 5. 再次验证标签里是否有 0 和 1
if len(np.unique(y_true_eval)) < 2:
    print("❌ 错误：评估数据中只包含一种类别（全是0或全是1），无法计算 AUC。")
    print("可能原因：裁剪后的区域正好避开了攻击区间。")
    exit()

# 6. 计算最终 AUC
auc = roc_auc_score(y_true_eval, y_scores_eval)

print("\n" + "="*40)
print(f"🌟 官方认证 AUC 得分: {auc:.5f}")
print("="*40)

if auc > 0.90:
    print("🚀 结论：完美复现！你的改进模型在官方标准下表现优异！")
elif auc > 0.80:
    print("👍 结论：表现良好，是一个有效的异常检测器。")
else:
    print("🤔 结论：分数稍低。看图分析：可能是因为左边那个 20000 处的波峰被官方标记为'正常'，但你的模型觉得它是'异常'（误报）。")

# 7. 画最终 ROC 图
fpr, tpr, _ = roc_curve(y_true_eval, y_scores_eval)
plt.figure(figsize=(8, 6))
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'Official ROC (AUC = {auc:.3f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Final Evaluation with Official Labels')
plt.legend(loc="lower right")
plt.grid(alpha=0.3)
plt.show()
