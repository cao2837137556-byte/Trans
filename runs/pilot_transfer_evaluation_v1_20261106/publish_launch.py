"""Publish fixed evaluation contract and actual launch snapshot with scoped staging."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,s):p.write_bytes(s.encode())
def js(p,v):write(p,json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def main():
    state=read(HERE/'CHAIN_STATE.json');assert state['stage'] not in ['STOP','WAITING_UPLOAD']
    assert state['dependency_gate']['status']=='PASS'
    for n,h in read(HERE/'DELIVERY.json')['pins'].items():
        assert sha(HERE/n)==h,n
        if n.endswith('.py'):ast.parse((HERE/n).read_text())
    assert read(HERE/'LOCAL_REGRESSION.json')['status']=='PASS' and read(HERE/'DEPENDENCY_REGRESSION.json')['status']=='PASS'
    js(HERE/'LAUNCH_SNAPSHOT.json',state)
    names=['.gitattributes','build_package.py','worker.py','scoreboard.py','test_evaluation.py','dependency_gate.py','test_dependencies.py','receiver.py','chain_client.py','prepare_delivery.py','publish_launch.py','progress.html','MODEL_PINS.json','INPUT_PINS.json','PARENT_PINS.json','SPEC.json','LOCAL_REGRESSION.json','DEPENDENCY_REGRESSION.json','DELIVERY.json','STARTUP_RECEIPT.json','START_RECEIPT.json','LAUNCH_SNAPSHOT.json']
    jobs=[]
    for phase in ['PREFLIGHT','AB','EDGE']:
        for kind in ['JOB','SCHEDULER']:
            v=state.get(phase+'_'+kind)
            if v:js(HERE/(phase+'_'+kind+'.json'),v);names.append(phase+'_'+kind+'.json')
        if state.get(phase+'_JOB'):jobs.append(state[phase+'_JOB']['job_id'])
    jobtext=', '.join(jobs);assert jobs
    design=DOC/'collab/20261106_pilot_transfer_evaluation_design_codex.md'
    report=DOC/'collab/20261106_pilot_transfer_evaluation_launch_codex.md'
    write(report,f'''结果：四组固定端点跨数据集评价已提交，作业{jobtext}；启动快照{state['stage']}，尚无最终新效果结论。
影响：原融合790及最近三轮小试全部评价，补齐A/B/Edge结果；三轮源侧NO_GO继续保留，不据此筛掉候选。
下一步：真实小切片工程门通过后自动AB→EDGE，更新右侧数据集成绩页；工程失败停止，科学失败照报。

# 2026-11-06 四组统一评价启动

见[冻结执行卡](20261106_pilot_transfer_evaluation_design_codex.md)。模型、原阈值/尺度、预处理、C5、数据身份与权重不变；不训练、不调阈值、不挑种子或端点。额外OLD782仅核验历史身份和原门。

27项远端已交付依赖在sbatch前PASS；本地11项评价回归和4项依赖回归PASS。真实Linux预检独立执行，本地回归不替代真实门。资源1CPU/8GiB，30＋45＋45分钟总计算上限2小时，排队另计，不自动重试。

进度页按数据集完成显示四组成绩，可切换RAW/C5、普通/原分层加权/Edge HT以及三种子/集成。直接目标正常FPR<2%、攻击查询检出>=99.9%，Edge HTTP/UDP分别判定；目标标签不替代原绝对/防退化/C5安全门。结果仍属已消费数据集上的开发泛化诊断。

用户现有SSH会话与SOCKS隧道复用；无新登录、VPN操作或环境重建。后台程序更新进度并取回重要摘要和SHA，完整模型与分数留超算。启动回执不代表真实预检通过或科学达标。
''')
    for p in [design,report]:write(Path(str(p)+'.sha256'),sha(p)+'  '+p.name+'\n')
    attr=DOC/'.gitattributes';rule=b'/collab/20261106_pilot_transfer_evaluation_* -text\n'
    if rule not in attr.read_bytes():attr.write_bytes(attr.read_bytes()+rule)
    history=DOC/'START_HERE_HISTORY.md';marker=b'## 2026-11-06 before pilot transfer evaluation\n\n';assert marker not in history.read_bytes()
    history.write_bytes(history.read_bytes()+b'\n\n'+marker+(DOC/'NEW_CHAT_START_HERE.md').read_bytes())
    write(DOC/'NEW_CHAT_START_HERE.md',f'''# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **四组统一评价已提交**：作业{jobtext}，启动快照{state['stage']}；真实预检→A/B→Edge，当前无最终新成绩。
2. **固定模型**：原FUSION790＋均匀/分层/受限三轮小试，三种子及集成全报；保持原阈值、尺度、输入与C5，不训练、不筛种子，旧源侧NO_GO保留。
3. **最终目标直观展示**：普通/加权FPR<2%、检出≥99.9%分列；Edge HTTP/UDP分别报告，HT单列。RAW与C5分别评价，保留原科学安全门。
4. **自动门与资源**：27项远端依赖、本地15项回归PASS；真实Linux门通过才完整评价。1CPU/8GiB、30＋45＋45分钟；工程失败停止，效果失败照报，不自动重试或训练。
5. **证据与存储**：[执行卡](collab/20261106_pilot_transfer_evaluation_design_codex.md)、[启动回执](collab/20261106_pilot_transfer_evaluation_launch_codex.md)；大文件留超算，[进度页](http://127.0.0.1:18806/)随数据集完成更新成绩。A/B/Edge均为开发泛化诊断。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
''')
    lead=f'''## 2026-11-06：四组模型A/B/Edge统一评价启动

用户授权原FUSION790＋最近三轮固定端点统一评价。作业{jobtext}、启动快照{state['stage']}；27项远端依赖和15项本地回归PASS，真实预检后自动AB→EDGE。1CPU/8GiB总上限2小时，无训练/调阈值/挑种子。直接展示误报<2%与检出≥99.9%，普通/加权/Edge HT分列，HTTP/UDP分别验收；RAW与C5及原门保留。源侧NO_GO不阻止本次诊断，也不改写为GO。大数组留超算，尚无新最终成绩。见[执行卡](collab/20261106_pilot_transfer_evaluation_design_codex.md)及[启动回执](collab/20261106_pilot_transfer_evaluation_launch_codex.md)。

---

'''
    for n in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/n;p.write_bytes(lead.encode()+p.read_bytes())
    js(HERE/'ARTIFACT_SHA256.json',{n:sha(HERE/n) for n in names})
    paths=[(HERE/n).relative_to(ROOT).as_posix() for n in names+['ARTIFACT_SHA256.json']]
    paths+=['runs/device_context_training_v1_20261105/index.html']
    paths += ['runs/mainline_docs/'+n for n in ['.gitattributes','NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md']]
    paths += [p.relative_to(ROOT).as_posix() for p in [design,report,Path(str(design)+'.sha256'),Path(str(report)+'.sha256')]]
    write(HERE/'.private/STAGE_PATHS.txt','\n'.join(paths)+'\n');print(json.dumps({'status':'SEALED','jobs':jobs,'stage':state['stage'],'paths':len(paths)}))
if __name__=='__main__':main()
