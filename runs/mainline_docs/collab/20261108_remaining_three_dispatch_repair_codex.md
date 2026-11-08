# 剩余三基线提交模块冲突修复

结果：182796在真实小切片通过后，因导入旧版controller导致提交接口不匹配而停止。新版本182804共享预检COMPLETED/0:0，计算节点启动回归及真实链路PASS，三个GPU方法作业已提交排队。
影响：三项新基线当时均未提交训练；DTE旧作业继续运行，CatBoost/SLAD结果保持。主模型、训练worker与CONFIG字节未改。
下一步：独立v2三个GPU方法排队，资源门通过后分别执行三种子训练与统一评价。

## 根因与漏检

worker为了复用封存依赖，将baseline_author_defaults_v1目录加入sys.path前端；真实pipeline又添加依赖路径。preflight末尾的通用`import controller`因此加载旧包，旧submit要求(method, seconds)，新调用只传method，出现`submit() missing 1 required positional argument: 'seconds'`。

前次局部回归覆盖训练恢复/重新加载预测，未覆盖真实初始化后的作业提交包装器。属于本次工程交付漏检，不是资源不足、模型训练失败或数据评价结果异常。

## 修复与永久门

- 独立目录baseline_remaining_three_v2_20261108，保留失败v1，不修改仍在运行的父包。
- controller从当前文件相邻的绝对路径加载，断言模块路径、worker路径、运行目录和submit签名；在真实pipeline前后均检查。
- 本地复现旧模块错误；用隔离临时目录和调度器桩走实际submit，验证正确脚本与重复调用只提交一次。
- 相同回归已在182804计算节点执行并PASS；真实提交仍由后续实际sbatch作业号确认，调度器桩不冒充真实GPU运行。
- 三方法本地跨进程参数更新及预测精确恢复重新通过。科学worker和CONFIG与v1逐字节相同。

## 工程记账与进度

182796 FAILED/1:0，墙钟260秒、分配8CPU，MaxRSS3757788K。其真实解码322679帧、编码112行的工程检查已PASS（编码误差0、fresh support误差0）；不能把260秒全部计为无效计算，也没有足够证据拆分精确有效/无效CPU时间。正式新训练数为0。

182804为8CPU24GiB2小时共享预检，后续GPU资源与训练合同不改。新进度客户端PID8748、接收端18879、页面18806；旧客户端35108核实身份后停止，失败182796仍作为历史记录展示。

## 实际提交验收

182804 COMPLETED/0:0，墙钟94秒、MaxRSS6565952K；真实pipeline后的LOCAL_CONTROLLER_GATE也PASS。源整组划分472627训练/145281验证，capture/session/component无交叉；四设备UDP攻击各仅一个独立组，按封存规则全部留训练并披露验证缺口，其他可分协议覆盖通过。没有使用目标分数。

实际GPU作业：Disent-AD182805、TabM182806、TabR182807，均PENDING，尚未运行GPU整轮资源检查，不宣称正式训练开始。六方法进度页已显示三个实际作业号。主模型/旧训练包未改。
