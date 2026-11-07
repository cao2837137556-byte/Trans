"""Negative identity controls, goal boundaries, historical scoreboard parity."""
import ast,json,hashlib
from pathlib import Path
import numpy as np
import worker as w
import scoreboard as b
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    passed=[]
    names=['OLD782','FUSION790'];arms={n:dict(cuts=np.zeros(4)) for n in names}
    saved={n+'_RAW':np.ones((2,4)) for n in names};scores={n:{'RAW':saved[n+'_RAW'].copy()} for n in names}
    assert all(v==0 for v in w.baseline_check(['a','b'],['a','b'],saved,scores,arms).values());passed.append('baseline exact')
    for case in ['uid','score','decision']:
        use={n:{'RAW':v['RAW'].copy()} for n,v in scores.items()};data={n:v.copy() for n,v in saved.items()}
        ids=['b','a'] if case=='uid' else ['a','b']
        if case=='score':use['OLD782']['RAW'][0,0]+=.1
        if case=='decision':use['OLD782']['RAW'][0,0]=.0001;data['OLD782_RAW'][0,0]=-.0001
        try:w.baseline_check(['a','b'],ids,data,use,arms)
        except AssertionError:passed.append('reject '+case)
        else:raise AssertionError(case)
    class Metrics:
        def gates(self,r):return dict(status='FAIL',mapped=r['primary']['FUSION790'])
    primary={n:n for n in ['OLD782',*b.ARMS]}
    gates=w.candidate_gates({'primary':primary},Metrics())
    assert all(gates[n]['mapped']==n and gates[n]['status']=='FAIL' for n in b.ARMS);passed.append('all arm gates attributed and failures retained')
    assert b.target(.02,[1.])=='FAIL' and b.target(.01999,[.999])=='PASS' and b.target(.01,[.99899])=='FAIL'
    assert b.target(None,[1.])=='NOT_EVALUABLE';passed.append('strict FPR inclusive recall missing denominator')
    old=ROOT/'runs/fusion_anchor_evaluation_v1_20261105'
    ab=read(old/'AB_RESULT.json')['pools'];edge=read(old/'EDGE_RESULT.json')['arms']
    for pool,v in ab.items():
        fake={n:v['primary']['FUSION790'] for n in b.ARMS};out=b.extract(fake)
        row=next(x for x in out if x['arm']=='FUSION790' and x['head']=='ensemble' and x['method']=='C5_P3' and x['basis']=='sample')
        assert row['target']=='PASS' and row['fp']==(22 if pool=='CIC_DEV' else 1299)
    fake={n:edge['FUSION790'] for n in b.ARMS};out=b.extract(fake,True)
    row=next(x for x in out if x['arm']=='FUSION790' and x['head']=='ensemble' and x['method']=='C5_P3' and x['basis']=='sample')
    assert row['fp']==1158 and row['fpr']==.0579 and row['http']==.94995 and row['udp']==.9866 and row['target']=='FAIL';passed.append('historical AB Edge scoreboard exact')
    pred={'FUSION790':{m:np.asarray([[0]*4,[1]*4],bool) for m in ['RAW','C5_P3']}}
    pred.update({n:{m:~v for m,v in pred['FUSION790'].items()} for n in b.ARMS[1:]})
    t=w.transitions({'rows':[{'label':0},{'label':1}]},pred)
    assert t['RISK_GUARDED']['RAW']['0']['added']==[1]*4 and t['RISK_GUARDED']['RAW']['1']['removed']==[1]*4;passed.append('paired added removed direction')
    def funcs(p):return {v.name:ast.dump(v,include_attributes=False) for v in ast.parse(p.read_text()).body if isinstance(v,ast.FunctionDef)}
    oldf,newf=funcs(old/'worker.py'),funcs(HERE/'worker.py')
    for n in ['load','forward','seed_errors','save_scores']:assert oldf[n]==newf[n],n
    passed.append('input preprocessing RAW C5 scoring unchanged AST')
    accepted=read(ROOT/'runs/device_context_evaluation_v1_20261105/FINAL_TRAINING_ACCEPTANCE.json')
    for name,p in read(HERE/'MODEL_PINS.json').items():
        source=ROOT/'runs'/p['folder']/'PILOT_RESULT.json'
        assert hashlib.sha256(source.read_bytes()).hexdigest()==p['receipt_sha256']
        for s,h in p['heads'].items():
            base=accepted['heads']['FUSION790_'+s];assert h['cut']==base['cut'] and h['scale']==base['scale']
        assert p['ensemble_cut']==accepted['ensembles']['FUSION790']['cut']
    passed.append('three pilot receipts original cuts scales match')
    tree=ast.parse((HERE/'worker.py').read_text());assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='set_num_interop_threads' for n in ast.walk(tree));passed.append('backend sole interop owner')
    out=dict(status='PASS',tests=passed,scope='LOCAL_NOT_REAL_LINUX')
    (HERE/'LOCAL_REGRESSION.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out))
if __name__=='__main__':main()
