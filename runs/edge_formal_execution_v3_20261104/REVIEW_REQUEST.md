# 供小anti独立复核：v3进度I/O集成

结果：用户确认181645预算停止后制作独立v3，当前源码、测试与交付包已准备；本文件是复核材料，不是已完成的独立复核。
影响：科学计算与监督/检查点实现未变，实时进度取消fsync；跨v2/v3产物不隐式迁移。
下一步：请给出可执行问题或PASS/CHANGES_REQUESTED及证据；在复核和真实Linux门完成前不宣称正式就绪。

复核入口：`worker.py`相对v2的两处集成、`progress_io.py`、`test_progress_io.py`、`test_v3_integration.py`、两张DRAFT卡、`LOCAL_ACCEPTANCE.json`与`DELIVERY_DELTA_MANIFEST.json`。

1. 两条路径是否均为非权威显示；runtime_control的终态写入和CURRENT提交顺序是否保持原样。
2. 模块patch仅在单线程replay作用域生效，异常是否恢复原writer；同名异目录、STOP与COMPLETE是否继续持久化。
3. helper是否进入完整依赖与科学绑定；交付闭包是否覆盖父版本字节比较文件及所有runtime依赖。
4. byte-identical科学核心和合成输入编排测试是否足够支撑当前“本地通过”范围；不得将其描述为真实Linux frozen-model同值结果。
5. v2完整NORMAL/HTTP已校验但不自动迁移；UDP部分角色仍拒绝复用，预算和权威回执检查没有放宽。

实际瓶颈证据位于`../edge_progress_io_optimization_v1_20261104`；181645停止与保留产物校验位于`../edge_gate_181645_closure_20261104`。未向外部服务发送复核消息，按既有collab文档方式交接。
