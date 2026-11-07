"""Build an isolated frozen-endpoint diagnostic evaluation; never edit parent runs."""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'runs/fusion_anchor_evaluation_v1_20261105'
PILOTS={'RISK_UNIFORM':'source_risk_preservation_pilot_v2_20261106','RISK_STRATIFIED':'source_stratified_pilot_v1_20261106','RISK_GUARDED':'source_guarded_pilot_v1_20261106'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,s):(HERE/n).write_bytes(s.encode())
def js(n,v):write(n,json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def main():
    assert not (HERE/'START_INTENT.json').exists();(HERE/'.private').mkdir(exist_ok=True)
    for n,h in json.loads((OLD/'DELIVERY.json').read_text())['pins'].items():assert sha(OLD/n)==h,n
    (HERE/'PARENT_PINS.json').write_bytes((OLD/'PARENT_PINS.json').read_bytes())
    pins={};models={}
    for arm,folder in PILOTS.items():
        p=ROOT/'runs'/folder;d=json.loads((p/'PILOT_RESULT.json').read_text());assert d['status']=='PASS'
        models[arm]={'folder':folder,'receipt_sha256':sha(p/'PILOT_RESULT.json'),'heads':{s:{k:h[k] for k in ['cut','scale','head_sha256','final_fingerprint']} for s,h in d['heads'].items()},'ensemble_cut':d['ensemble']['cut'],'source_scientific_status':'NO_GO'}
        pins[(p/'PILOT_RESULT.json').relative_to(ROOT).as_posix()]=sha(p/'PILOT_RESULT.json')
    js('MODEL_PINS.json',models)
    # Include only already-delivered runtime dependencies, not local-only audit scripts.
    ep=ROOT/'runs/device_context_evaluation_v1_20261105'
    for n,h in json.loads((ep/'DELIVERY.json').read_text())['pins'].items():pins[(ep/n).relative_to(ROOT).as_posix()]=h
    for n,h in json.loads((HERE/'PARENT_PINS.json').read_text()).items():pins[(ep/n).relative_to(ROOT).as_posix()]=h
    js('INPUT_PINS.json',pins)
    (HERE/'dependency_gate.py').write_bytes((ROOT/'runs/source_guarded_pilot_v1_20261106/dependency_gate.py').read_bytes())
    (HERE/'test_dependencies.py').write_bytes((ROOT/'runs/source_guarded_pilot_v1_20261106/test_dependencies.py').read_bytes())
    src=(OLD/'worker.py').read_text()
    start=src.index('def initialize():');end=src.index('\ndef baseline_check',start)
    src=src[:start]+'''def initialize():
    for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,'DELIVERY:'+n
    import dependency_gate
    dependency_gate.verify(HERE.parents[1],read(HERE/'INPUT_PINS.json'))
    for n,h in read(HERE/'PARENT_PINS.json').items():assert sha(EVAL/n)==h,'PARENT:'+n
    sys.path.insert(0,str(EVAL));import common as c
    c.verify();c.progress=progress
    import inputs,edge_context,metrics,reporting
    inputs.progress=edge_context.progress=progress
    k,norm,oldarms=c.models();arms={n:oldarms[n] for n in ['OLD782','FUSION790']}
    import torch
    for name,contract in read(HERE/'MODEL_PINS.json').items():
        base=HERE.parent/contract['folder'];receipt=read(c.pin(base/'PILOT_RESULT.json',contract['receipt_sha256']))
        assert receipt['status']=='PASS' and not receipt['threshold_refit'] and not receipt['encoder_finetuned']
        assert contract['ensemble_cut']==receipt['ensemble']['cut']==arms['FUSION790']['cuts'][3]
        nets=[]
        for j,seed in enumerate([27,127,227]):
            h=contract['heads'][str(seed)];r=receipt['heads'][str(seed)]
            assert not r['runtime_gate_only'] and r['epochs']==5
            assert all(r[key]==value for key,value in h.items()),'HEAD_RECEIPT'
            assert h['cut']==arms['FUSION790']['cuts'][j] and h['scale']==arms['FUSION790']['scales'][j],'FROZEN_CUT_SCALE'
            path=c.pin(base/'heads'/str(seed)/'head.npz',h['head_sha256'])
            net=k.classifier(seed,790)
            with np.load(path,allow_pickle=False) as a:net.load_state_dict({key:torch.from_numpy(a[key].copy()) for key in a.files},strict=True)
            net.eval().requires_grad_(False);nets.append(net)
        arms[name]=dict(models=nets,dimension=790,cuts=arms['FUSION790']['cuts'].copy(),scales=arms['FUSION790']['scales'].copy())
    assert list(arms)==['OLD782','FUSION790','RISK_UNIFORM','RISK_STRATIFIED','RISK_GUARDED']
    return c,k,norm,arms,inputs,edge_context,metrics,reporting
''' + src[end:]
    src=src.replace("for arm in ['OLD782','REFIT782','STATS8','FUSION790']:","for arm in ['OLD782','FUSION790']:")
    start=src.index('def candidate_gates(');end=src.index('\ndef load(',start)
    src=src[:start]+'''def candidate_gates(report,metrics):
    original=report['primary'];out={}
    for name in ['FUSION790','RISK_UNIFORM','RISK_STRATIFIED','RISK_GUARDED']:
        mapped={'primary':{'OLD782':original['OLD782'],'FUSION790':original[name]}}
        out[name]=metrics.gates(mapped);out[name]['evaluated_candidate']=name
    return out

def transitions(data,pred):
    ix=data['views']['primary'][0] if 'views' in data else np.arange(len(data['rows']))
    rows=data['rows'];out={}
    for arm in ['RISK_UNIFORM','RISK_STRATIFIED','RISK_GUARDED']:
        out[arm]={}
        for method in ['RAW','C5_P3']:
            out[arm][method]={}
            for label in [0,1]:
                ids=ix[np.asarray([rows[int(i)]['label']==label for i in ix])]
                old=pred['FUSION790'][method][ids];new=pred[arm][method][ids]
                out[arm][method][str(label)]=dict(rows=len(ids),added=(new&~old).sum(0).tolist(),removed=(old&~new).sum(0).tolist(),unchanged=(new==old).sum(0).tolist(),head_order=['27','127','227','ensemble'])
    return out

def update_board(pool,report,edge=False):
    import scoreboard
    path=HERE/'BOARD.json';board=read(path) if path.exists() else {}
    board[pool]=scoreboard.extract(report,edge)
    write('BOARD.json',board)
''' + src[end:]
    src=src.replace("full_metrics_sha256=sha(HERE/(pool+'_METRICS.json')),scores=save_scores(pool,d,scores))","full_metrics_sha256=sha(HERE/(pool+'_METRICS.json')),transitions_vs_fusion=transitions(d,pred),scores=save_scores(pool,d,scores))\n            update_board(pool,m['primary'])")
    src=src.replace("seed_errors=seed_errors(d,pred),scores=save_scores('EDGE',d,scores))","seed_errors=seed_errors(d,pred),transitions_vs_fusion=transitions(d,pred),scores=save_scores('EDGE',d,scores))\n        update_board('EDGE',reports,True)")
    src=src.replace("TRAIN=HERE.parent/'fusion_score_anchor_v2_20261105';PHASE", "PHASE")
    src=src.replace('Frozen five-arm evaluation.','Four requested arms plus OLD782 identity/legacy-gate control.')
    write('worker.py',src)
    receiver=(OLD/'receiver.py').read_text().replace('18852','18859').replace('ANCHOR_EVALUATION_COMPLETE','PILOT_TRANSFER_EVALUATION_COMPLETE').replace('anchor-eval','pilot-transfer')
    receiver=receiver.replace("def run(phase,minutes):","def run(phase,minutes):\n    import dependency_gate\n    write('DEPENDENCY_GATE.json',dependency_gate.verify(PROJECT,read('INPUT_PINS.json')))" )
    receiver=receiver.replace("run(phase,30 if phase=='PREFLIGHT' else 60)","run(phase,30 if phase=='PREFLIGHT' else 45)")
    receiver=receiver.replace("d['runtime_forecast']=read('RUNTIME_FORECAST.json')","d['runtime_forecast']=read('RUNTIME_FORECAST.json')\n    d['dependency_gate']=read('DEPENDENCY_GATE.json')\n    d['scoreboard']=read('BOARD.json')")
    write('receiver.py',receiver)
    client=(OLD/'chain_client.py').read_text().replace('18852','18859').replace('ANCHOR_EVALUATION_COMPLETE','PILOT_TRANSFER_EVALUATION_COMPLETE').replace('EVAL_ANCHOR_V1','PILOT_TRANSFER_EVAL_V1')
    write('chain_client.py',client)
    prep=(OLD/'prepare_delivery.py').read_text().replace('18852','18859').replace('ANCHOR_EVALUATION','PILOT_TRANSFER_EVALUATION').replace('FIVE_ARM_FROZEN_EVALUATION','FOUR_ARM_FROZEN_PILOT_TRANSFER_EVALUATION')
    prep=prep.replace("'REMOTE_TRAINING_PINS.json','TRAINING_ACCEPTANCE.json'","'MODEL_PINS.json','INPUT_PINS.json','dependency_gate.py','test_dependencies.py','scoreboard.py'")
    prep=prep.replace('evaluation_phase_seconds=3600','evaluation_phase_seconds=2700')
    write('prepare_delivery.py',prep)
    js('SPEC.json',dict(version=HERE.name,arms=['FUSION790',*PILOTS],identity_control='OLD782',seeds=[27,127,227],ensemble='fixed arithmetic mean float64',pools=['CIC_DEV','UNSW_DEV','EDGE'],phases=['PREFLIGHT','AB','EDGE'],cpu=1,memory_gib=8,wall_minutes=[30,45,45],training=False,threshold_fitting=False,scale_fitting=False,C5='original support, q14 guard, lambda=.25 cubic kernel, original per-seed FUSION790 scales',goals={'FPR':'strictly < 0.02','attack_recall':'>= 0.999','AB':['ordinary','hierarchical weighted'],'EDGE':['selected sample','HT population estimate','hierarchical weighted separate'],'HTTP_UDP_separate':True},endpoint='all three pilots fixed fifth-round endpoint, no source-GO filtering',scope='Development cross-dataset generalization diagnostics; not untouched external confirmation',scientific_failures_do_not_stop_evaluation=True,automatic_training=False,automatic_retries=0,large_artifacts='HPC only',historical_pilot_NO_GO_preserved=True))
    write('.gitattributes','* -text\n')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    print('BUILT',len(pins),'dependencies')
if __name__=='__main__':main()
