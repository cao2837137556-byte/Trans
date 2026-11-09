"""Draw the manuscript's conceptual architecture, without experimental data."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent
font = Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['svg.fonttype'] = 'path'
fig, ax = plt.subplots(figsize=(14, 7.6))
fig.patch.set_facecolor('white')
ax.set(xlim=(0, 1), ylim=(0, 1))
ax.axis('off')

def box(x, y, w, h, title, body, color='#eaf2f8'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.008,rounding_size=0.012',
                              linewidth=1.2,edgecolor='#435466',facecolor=color))
    ax.text(x+w/2,y+h-.025,title,ha='center',va='top',fontsize=12,fontweight='bold',color='#152d44')
    ax.text(x+w/2,y+h/2-.018,body,ha='center',va='center',fontsize=10.2,linespacing=1.65,color='#263747')

def arrow(p, q, dashed=False):
    ax.add_patch(FancyArrowPatch(p,q,arrowstyle='-|>',mutation_scale=14,linewidth=1.35,
                               color='#52667c',linestyle='--' if dashed else '-'))

ax.axhspan(.76,.99,color='#f3f5f7')
ax.text(.018,.97,'离线准备：参数与阈值固定后进入评价',fontsize=12,fontweight='bold',va='top',color='#263747')
box(.025,.785,.245,.13,'源训练与表示','编码器 / 融合分类头\n源归一化统计量')
box(.365,.785,.285,.13,'源几何与分数尺度','半径：由源正常样本估计\n离散尺度：由源训练分数估计')
box(.745,.785,.23,.13,'源正常校准','1% 加权误报预算\n固定告警阈值 τ')
ax.text(.018,.72,'现场推理：仅使用已观测前缀与时间合格的正常参考',fontsize=12,fontweight='bold',color='#263747')

box(.025,.405,.16,.205,'当前查询','当前包\n已观测流量前缀')
box(.235,.405,.195,.205,'联合表示','编码表示 z\n当前包描述 q\n1秒 / 10秒上下文 c')
box(.50,.535,.195,.14,'基础判别','固定融合分类器\n攻击分数 a', '#eaf2f8')
box(.50,.25,.195,.205,'正常支持','设备 / 协议 / 时间资格\n三空间交集\n组件内最近参考\n跨组件第二小值', '#e9f4ef')
box(.235,.10,.195,.17,'正常参考资料','可信试运行与历史\n查询时已可获得', '#e9f4ef')
box(.775,.405,.20,.22,'有界分数修正','支持度 s → 扣分强度 g(s)\n减去 $\\lambda b_k g(s)$\nTCP保护条件成立时旁路', '#fff2dd')
box(.775,.10,.20,.15,'固定工作点判决','三头修正分数取均值\n均值 > τ 时告警', '#fff2dd')

arrow((.185,.505),(.235,.505))
arrow((.430,.56),(.50,.60))
arrow((.430,.44),(.50,.36))
arrow((.430,.205),(.50,.30))
arrow((.695,.60),(.775,.57))
arrow((.695,.355),(.775,.455))
arrow((.875,.405),(.875,.25))
ax.text(.713,.62,'分数',fontsize=9,color='#52667c')
ax.text(.715,.37,'支持',fontsize=9,color='#52667c',rotation=30)
ax.text(.025,.035,'上方为离线固定配置，下方为现场推理的主要数据路径。上下文同时用于基础判别与正常参考约束。',fontsize=10,color='#52667c')
fig.subplots_adjust(left=.015,right=.985,top=.99,bottom=.015)
fig.savefig(OUT/'context_reference_architecture_codex.svg',bbox_inches='tight')
fig.savefig(OUT/'context_reference_architecture_codex.png',dpi=160,bbox_inches='tight')
plt.close(fig)
