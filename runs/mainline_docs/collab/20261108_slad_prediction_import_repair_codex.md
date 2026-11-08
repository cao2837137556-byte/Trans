# SLAD 独立评价加载修复

结果：182779在SLAD_EVALUATE阶段失败，原因ModuleNotFoundError: No module named algorithms；三种子各100轮训练均已PASS。独立评价修复182782已提交并运行，1CPU/8GiB/2小时。
影响：故障发生于torch.load反序列化SLAD对象，未开始有效评价；不属于超时、OOM或训练未收敛。复用三个完整模型，不改训练结果或参数、不触碰仍在运行的DTE-C封存包。CatBoost182781已完成，尚待整体科学验收。
下一步：修复作业重新执行真实因果小切片链路，校验三模型SHA并从纯评价进程加载/预测，通过后直接补跑CAL与A/B/Edge。进度已合并至既有18806页面，客户端PID34636接替旧状态客户端。

## 根因与永久检查

原formal.predictor在torch.load前没有将vendor/slad加入模块搜索路径。保存的对象需要algorithms.slad.SLAD、algorithms.base_networks等作者类。此前跨进程续训检查先construct模型，间接注册路径，因此没有覆盖直接predictor加载路径。

独立runner显式注册封存作者模块路径；模型、损失、预处理、训练轮数、评分、阈值口径均不变。原formal.py保持原字节以免DTE末尾依赖门失败。回归检查必须在全新、未construct的子进程直接调用predictor：旧路径准确复现同报错，修复后预测与保存前逐元素一致，本地已通过。Linux对三个真实100轮模型各32条CAL行重复回读一致性仍由作业内门执行，不以本地代替。

## 保留的有效工作

三种子训练结果：27/127/227，各134493正常训练行、100轮；训练阶段子进程wall分别309.747、306.478、307.981秒，评价失败进程13.197秒。总作业953.217秒中其余为编排开销，不把全部953秒计为无效计算。

模型SHA：
- 27：6cc7851835472df3ca72e5bf22533be4580ef7a86cb9635c6a2afa756dfc1e5d
- 127：986a6dcd51714ae4e6d6fce921bcaa940c337e999260a4b45938b43fb9f94b18
- 227：554fe786e0dcd865b8c5397be2b8fadeeaae1b910e5e76f02de670f9587a4465

新目录baseline_slad_eval_repair_v1_20261108只通过只读使用的链接引用已封存大数组/模型；新分数与汇总写入新目录，旧失败回执保留。评价前后校验模型SHA。无新训练，无新登录，无环境重建。

## 其他方法即时状态

修复提交时DTE-C182778正常，种子27完成、127约122/400轮；CatBoost182781 COMPLETED/0:0、1:10:13，训练与评价运行回执PASS，尚未做论文主表验收。进度页SLAD绑定新作业182782并保留previous_failed_job182779，失败状态不会混淆成DTE/CatBoost停止。

[独立加载回归](../../baseline_slad_eval_repair_v1_20261108/LOCAL_REGRESSION.json) · [父工件SHA](../../baseline_slad_eval_repair_v1_20261108/PARENT_PINS.json) · [修复runner](../../baseline_slad_eval_repair_v1_20261108/runner.py)
