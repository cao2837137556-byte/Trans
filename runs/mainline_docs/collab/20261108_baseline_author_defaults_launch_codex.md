# 作者固定参数基线首批启动

结果：自动执行链已提交182777，1CPU/12GiB/2小时；计算节点环境门已实跑PASS。本轮无调参搜索，主模型冻结。
影响：首批DTE-C、SLAD、CatBoost各自资源与实现门通过后自动提交正式三种子训练、CAL和A/B/Edge评价，不再等待人工二次确认。尚未取得正式训练完成或检测指标。
下一步：普通客户端持续更新现有进度页并回收小回执；另外四方法保留真实资格待办，不宣称七种基线均已放行。

## 配置核实与执行

DTE-C使用封存官方DTECategorical默认400轮、batch64、Adam 1e-4、weight_decay5e-4、T400/7bins；SLAD默认100轮、batch128、lr1e-3、Adam weight_decay1e-5，epoch_steps=-1完整轮次；CatBoost1.2.8默认1000树、官方自动学习率并记录最终get_all_params。恢复预检的少量轮次不能冒充正式训练。共享790适配与三种子27/127/227固定，CAL正常33147行按原层级权重校准1%阈值，严格大于；目标池不选参数、轮次、种子。

作者证据：封存[执行卡](../../baseline_author_defaults_v1_20261108/EXECUTION_CARD.md)和[逐方法配置](../../baseline_author_defaults_v1_20261108/CONFIG.json)。官方[TabM示例](https://github.com/yandex-research/tabm/blob/b53fd7cf2d9be2d66b918ca6cf66e0365e4ce11c/example.ipynb)需要patience16早停，不能为了省验证而随意改成固定少轮。TabR已取得官方CA/adult相同default-evaluation配置，d_main265及optimizer有出处，但历史mixer_dropout到当前context_dropout的语义绑定还要核实，先前d_main128仅工程探针。Disent-AD的配置按原数据集变化，不存在针对790的唯一推荐参数。ModernNCA默认采样率.5不改，单张量30.89GiB下界并非全反传内存资格。

## 工程门与预算

本地14项（语法、DTE/SLAD独立进程完整下一轮参数精确一致、SLAD检查点大小）通过；这不替代Linux复验。计算节点ENVIRONMENT已PASS，真实因果解码/重新编码/距离及本轮完整资源门仍在自动执行。预检12GiB依据此前CatBoost约6.3GiB峰值及全量数据准备余量；方法作业各1CPU/12GiB，时间按本轮实测三种子训练1.5倍、评分2倍及固定余量决定，单方法最多24小时。超出明确资源待办，不截少轮模型充结果，不自动重交失败作业。

DTE/SLAD只在各方法目录保存状态，SLAD不逐轮重复序列化巨大变换训练数据。CatBoost开启官方快照；未验证其原生快照跨进程连续性，不能宣称精确续训已通过，当前是完整预算独立训练，不以init_model增树代替续训。所有最终评分从磁盘新进程加载。源与目标大数组、模型及全量分数只留超算；本地仅汇总和SHA。

首批结果包含A/B full和primary、逐设备与协议/场景、Edge普通与HT、四头及普通AUROC/AUPRC。主模型保持原冻结结果。共享790 RAW比较与享有额外正常参考的主系统C5成绩须分开说明；当前没有新评价成绩。

## 交付身份

- 运行目录：baseline_author_defaults_v1_20261108；89材料SHA、25远端依赖。
- 已提交预检：182777。正式方法作业号由通过门后的RELEASE和各方法JOB回执记录。
- 普通客户端PID29824；复用既有SSH，未新登录、未重建环境。
- 进度：[本地页面](http://127.0.0.1:18806/)。首批完成不等于整个七方法计划完成。
