"""Write the repair handoff only after real submission/startup receipts exist."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PACKAGE=HERE.parent/'history_sample_coverage_c4_header_repair_v1_20261101'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sub=read(HERE/'SUBMIT_RECEIPT.json');start=read(HERE/'STARTUP_VERIFICATION.json')
assert sub['submitted'] and sub['job_id'].isdigit()
assert start['progress_page_status']==200
assert sub['header_qualification']['packets']==246
job=sub['job_id'];state=start['state'];scheduler=state.get('squeue') or state.get('sacct')
name='20261102_b_sample_fpr_c4_true_false_header_repair_and_submission_codex.md'
doc=ROOT/'runs/mainline_docs/collab'/name
text=f'''# C4 TCP 标志位校验修复与续跑提交

2026-11-02。用户授权修复并重新提交同一 C4 候选；没有更改科学方案。

作业 **{job}** 已实际提交；启动核验的调度状态为 `{scheduler}`。
进度仍在 Codex 右侧 `http://127.0.0.1:18789/`。普通程序自动更新、取回、历史 DEV 门及唯一一次 A/B 验收；不持续 AI 监测。提交/运行不等于最终通过。

## 本次故障与实证修复

180591 在 Netatmo 第二遍第一个 MPEG 告警帧附近停止，子进程真实错误为 `AUDIT_INVALID_INTEGER:tcp.flags.syn`。固定 TShark 4.6.6 的 TCP 布尔字段实际输出 `True/False`，新增原包头校验器错误地按整数解析。这是工程校验错误，未进入 Netatmo 模型编码或候选评价。

此前合成检查未覆盖实际字段表示。本次随机读取全部 246 个已知告警原包，保持 SHB/IDB 和 EPB 字节，用固定解码字段/选项生成静态资格切片，再映射回原逻辑帧。实际 SYN=False 246、ACK=True 246、RST=False 246；FIN=False 245、True 1。原始包头独立核验 **246/246 PASS**。

修复只将四个布尔标志字段改为严格布尔解析；整数、地址、长度、时间、原包索引核验继续执行。未知文本/多值/缺失/错误位仍拒绝。静态切片不替代完整连续 RECENT 重放；正式运行仍须完整 endpoint 对账、解码 exit=0、492 条 MPEG 诊断的协议/帧多重集一致及246个原包头审计。

## 恢复边界

- TP Link/WEMO Power/Samsung 已完成 **20,480** 条编码，校验后复用。
- Netatmo 完整候选清单 **3,592,947** 条（REF 2,612,450、DEV 980,497）、索引和既定选点（REF 8,192、DEV 4,096）复用180591副本。
- 后续 census 主库只读打开；新名字使用硬链接或校验复制。选点收据路径显式迁移，行字节/UID pin保持；编码前仍独立重放选点。清理只解除本轮新名字，历史检查点保留。
- Netatmo 未完成的连续上下文从帧1重放；不声称从失败帧原地续算。随后仅做剩余12,288条编码和原合同验收。
- 本次实际上传修复代码4,741,120字节；远端2,405,307,756字节输入已存在并校验，未重传。

累计原8小时预算扣费9064 + 14687 + 783 = **24,534秒**，剩 **4,266秒（71分6秒）**，包括后续编码与本地评价，未重置预算。资源仍4CPU/8GiB/20GiB，编码36864、距离10亿上限；排队/网络不作为完成时间保证。若预算不足会停止，不能将停止写为科学失败或通过。

## 验证与封存

- 本地59项工程测试、8项交付测试通过；全部246个真实包头核验通过。
- 超算Python3.11.11/NumPy2.0.1/Torch2.5.1与固定环境通过；超算59项检查及246个真实包头资格通过，三个旧设备编码及Netatmo索引清单核验通过。
- 下游只读保存数组复现：A179886/B148316四头、双视图、C2守卫精确一致；旧DEV12288行及旧参考24163行对齐通过，无新模型或距离。
- 科学选择器、盐值、容量、λ=.25、模型、阈值、C2守卫及原门不变；A/B仍 `CONSUMED_DEVELOPMENT_ONLY`，B全部攻击命中守卫，不证明ACK/UDP保护。
- 新执行卡SHA256：`{sha(PACKAGE/'EXECUTION_CARD.json')}`。
- 真实包头证据：`../{HERE.name}/REAL_HEADER_AUDIT.json`，SHA256 `{sha(HERE/'REAL_HEADER_AUDIT.json')}`。
- 实际提交收据：`../{HERE.name}/SUBMIT_RECEIPT.json`，SHA256 `{sha(HERE/'SUBMIT_RECEIPT.json')}`。
- 启动核验：`../{HERE.name}/STARTUP_VERIFICATION.json`。
- 最终以 `../{PACKAGE.name}/FINAL_ACCEPTANCE.json` 为准；当前没有新的C4科学成绩。
'''
assert not doc.exists()
doc.write_text(text,encoding='utf-8')
doc.with_name(doc.name+'.sha256').write_text(sha(doc)+'  '+doc.name+'\n',encoding='utf-8')
pointer=f'**2026-11-02 C4 180591 的 TCP True/False 包头校验故障已修复，续跑已提交 {job}：** [真实246包资格、检查点复用、累计预算与提交回执](collab/{name})。59项本地/超算工程检查、8项交付检查及246/246真实包头核验通过。复用三设备20480编码及Netatmo完整候选/索引/既定选点，只重放未完成上下文再编码验收；原预算剩4266秒，未重置。右侧18789自动更新，不持续AI监测；当前没有新科学成绩。下方180591运行中等为历史快照。\n\n'
for name in ('NEW_CHAT_START_HERE.md','CURRENT_PROBLEM_BRIEF_20261025.md'):
    p=ROOT/'runs/mainline_docs'/name;before=p.stat().st_mtime_ns
    s=p.read_text(encoding='utf-8');first,sep,rest=s.partition('\n')
    assert p.stat().st_mtime_ns==before
    p.write_text(first+sep+'\n'+pointer+rest.lstrip('\n'),encoding='utf-8')
print(json.dumps(dict(document=str(doc),sha256=sha(doc),job_id=job),ensure_ascii=False))
