# 扩大评估启动停止与 V2 入口修复

2026-09-10。**首次真实启动已停止，没有新测试结果；修复只涉及启动入口。**

V1监督器PID62120、worker62196，1.062秒后worker exit1。停止发生在worker
`readiness()`的Git HEAD复核；尚未导入推理执行器、解码原始成员或载入真实模型。
包处理0、模型载入/推理0、训练0。原失败目录已封存，进程均退出，零自动重试。

## 确证原因与实现责任

`C:/Program Files/Git/cmd/git.exe`是46,480字节的启动包装器，需要再创建真正Git进程。
worker＋包装器已经占满Windows Job的两进程限制，因此出现`error launching git`。
父监督器的就绪检查在Job外，所以先通过；原合成测试验证了失败停止，却没有覆盖
Job内实际Git路径启动，这是本次实现验收遗漏。不是数据、前端语义或模型能力失败。

四项无数据检查确证：同一两进程Job内包装器失败可复现；直接调用
`C:/Program Files/Git/mingw64/bin/git.exe`时HEAD和分支读取均通过，非法ref仍拒绝。
真实HEAD仍为`4b28747b09480471e2bac1beb3a9badf27280efb`，分支未改变。
Git本体SHA：`fc0f1cae1304fcdcf4d0749f421c5ed21471efc856301f92f56d4b844be84363`。

## 修复版交付及边界

新增V2控制器直接使用并核验Git本体；保留两进程和所有资源限制。使用独立输出
`runs/frontend_expanded_eval_v2_20260910/`，该目录尚未创建。直接复用V1已封存的
目标名单、配置与原始输入身份；前端物化、模型推理、指标算法的源码完全不变。
不重做名单准备、ZIP全量哈希、合成前端审计或真实资源试验。

修复封存：`runs/frontend_expanded_eval_startup_diagnosis_v2_20260910/`；包括可复现
生成脚本、四项Git路径试验、V2源码/入口脚本SHA。原23项科学输入/指标测试仍有效。
完整封存V2入口在真实两进程Job内的无数据就绪验收，以及缺少新授权时必须拒绝启动
的检查，另存`runs/frontend_expanded_eval_v2_startup_verification_20260910/verification.json`。
启动脚本`scripts/start_frontend_expanded_eval_local_v2.ps1`要求新的明确授权文字参数。

本次范围是异常停止、零重试，所以修复实现与无数据校验可继续，新的真实尝试需要
用户明确授权。没有自动重新解码或评分，也没有在旧失败目录内修改后继续运行。
获准后只执行相同262,050目标固定AB评估，异常仍停止、不重试；模型、阈值、seed、
冻结科学分母、真正FINAL边界及历史FAIL保持。

solved: 启动器/Job进程数冲突已复现，直接Git入口修复已实现。
changed_mainline: no，仍需完成现有AB的扩大攻击＋正常OOD评估。
active_blocker: 新的真实启动需要用户授权；当前没有新的模型效果结果。
frozen: V1实现和失败记录、模型/输入/阈值/seed/分母、零自动重试。
superseded: “本次扩大测试正在运行”的状态；其启动记录保留为历史。
next_action: 经新授权执行V2一次，完整结果由终态核验发布。
