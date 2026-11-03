# AB 起点对照：设计审查与冻结记录

2026-09-12。结论：PASS_STATIC_DESIGN_REVIEW，允许进入后续实现工作；未授权或执行真实T/E。
用户当前范围来自“下一步是方案定稿与审查”后的“明白了，那就动手下一步”。

冻结对象：
- `frontend_ab_start_control_design_v1_20260912.md` SHA256：`a37e55fc2550bb35660d4cd28c5cb50c42930cb628c697f3ff6ec8492cb2f825`。
- `frontend_ab_start_control_recipe_v1_20260912.json` SHA256：`5ce8f2e39c62c20eb8c23ee4d7462d77f038665c77da46d1be793eae9c7699ee`。

主审完成原配方、已封存AB/教师元数据与旧代码静态核对；独立科学审查与执行接口审查均通过。
未以合成测试通过或静态审查通过代替科学能力通过。新实现尚不存在，本轮没有运行模型测试。

## 已解决的具体问题

1. 新臂ID为C0_AB/R_AB，避免历史C0/R分数覆盖；C0仅标签，R完整保留原四项。
2. 训练起点及历史暴露明确：每臂额外3940步/301460呈现；AB谱系此前额外226840次B呈现。
3. 完整AB状态独立复制、空AdamW、原20轮顺序；head不重置，D零初始化不消耗RNG。
4. AB起点Aguard可非零，不改Aguard、尺度、白名单或loss去满足旧A初始化断言。
5. 不新增P阶段；T入口直接验证和消费旧封存缓存。旧load_prepared会重derive且要求当前
   recipeSHA，故新实现必须按本方案适配生产/消费身份；不能原样套用后再擅改冻结规则。
6. 旧AB终态字段verdict.status与旧aligned-P的status分别核验；不能混用schema。
7. C0教师/guard训练计数为0，日志无0/0；R固定187580教师呈现和967530保护对呈现。
8. 原六项开发方向性判读不变。1%是描述工作点，非新绝对门槛；0.1%另报风险。
   两个新臂均与AB和旧P2参照审阅，新臂相互比较不能掩盖共同退化。没有隐含容忍线。
9. 尾部LESS/EQUAL/GREATER按1%和0.1%分别报告；不自动选胜者，不进行尾部样本挖掘或调阈值。
10. T→E正常转移可由一次未来明确授权覆盖；实现范围内的常规修复/验收不重复求逐项许可。

## 核验范围

- 分支codex/exp-mainline；HEAD4b28747b09480471e2bac1beb3a9badf27280efb。
- 32项输入文件字节pin核验通过；checkpoint仅散列字节、读取已存receipt，没有torch.load。
- 40项原Python源文件hash保持；8项既有无关tracked文件hash与已封存实现配置一致。
- JSON结构、臂数/顺序、20×197预算、TRAIN/CHECK/expanded分母、累计暴露算术一致。
- 同会话文献原始摘要已核对，适用边界和未采用方法写入设计；无数据下载或新教师。
- 新方案实现/生成验收尚未执行；新真实模型载入、forward、optimizer、原始包解码均为0。

原F4 PASS、历史严格继承FAIL、Q/R科学TRADEOFF、联合NOT_REACHED、入网NOT_EVALUATED保持。
下一步是实现与生成数据验收。真实运行复用旧P，未来授权范围可为一次T→E；没有自动启动。
