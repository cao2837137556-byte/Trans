"""Regression against all frozen A/B p3 decisions, plus weighting/guard boundaries."""
import ast,json,sys
from pathlib import Path
import numpy as np
from common import correction,four,HERE,read,write,sha
import metrics

def main():
 root=HERE.parents[1]
 for p in HERE.glob('*.py'):ast.parse(p.read_text())
 freeze=read(HERE/'METHOD_FREEZE.json');cuts=np.asarray(freeze['calibration']['cuts']['cuts']+[freeze['calibration']['cuts']['ensemble_cut']]);scales=np.asarray(freeze['calibration']['scales']['scales'])
 plan=read(root/'runs/device_context_training_v2_20261105/ASSET_PLAN.json');assets=read(HERE/'ASSET_PLAN.json');checks={}
 for pool in ('CIC_DEV','UNSW_DEV'):
  rep=np.load(root/assets[pool+'_replay']['relative']);old=np.load(root/assets[pool+'_old_logits']['relative'])
  q=np.load(root/next(v['local_relative'] for v in plan.values() if v['name']==pool+'_q.npy'))
  assert np.array_equal(rep['uid'],old['uid']);support=rep['kernel_support'][rep['candidate_names'].tolist().index('1')]
  corrected=four(correction(old['head'].astype(np.float64),support,q,scales));actual=corrected>cuts
  expected=rep['decisions'][rep['candidate_names'].tolist().index('3')];assert np.array_equal(actual,expected)
  checks[pool]=dict(rows=len(q),p3_decisions_verified=int(actual.size),replay_sha256=sha(root/assets[pool+'_replay']['relative']))
 raw=np.arange(12,dtype=float).reshape(4,3);q=np.zeros((4,14));q[1,[0,2]]=1
 out=correction(raw,np.asarray([0,1,.5,1]),q,np.asarray([1.,2.,3.]));assert np.array_equal(out[:2],raw[:2]) and np.all(out[2:]<raw[2:])
 p=np.asarray([True,False,False]);m=metrics.rate(np.asarray([0,1]),p,np.asarray([.1,.9,20.]));assert m['weighted_rate']==.1 and m['unweighted_rate']==.5
 assert metrics.rate([],p,np.ones(3))['weighted_rate'] is None
 rows=[dict(device='d',protocol=17,scenario='attack',source_role='attack',label=1),dict(device='d',protocol=17,scenario='normal',source_role='NORMAL',label=0)]
 good=np.asarray([[True]*4,[False]*4]);bad=np.zeros((2,4),bool)
 r=metrics.summarize(rows,{'OLD782':{'RAW':good},'FUSION790':{'RAW':good}},{'primary':(np.arange(2),np.ones(2))});assert metrics.gates(r)['status']=='PASS'
 r=metrics.summarize(rows,{'OLD782':{'RAW':good},'FUSION790':{'RAW':bad}},{'primary':(np.arange(2),np.ones(2))});assert metrics.gates(r)['status']=='FAIL' and metrics.gates(r,cal=True)['status']=='FAIL'
 write('LOCAL_REGRESSION.json',dict(status='PASS',checks=checks,zero_support_syn_guard=True,conditional_weighting=True,scientific_failure_reporting=True,linux_real_gate='PENDING'))
 print('LOCAL_EVALUATION_REGRESSION_PASS',sum(c['p3_decisions_verified'] for c in checks.values()))

if __name__=='__main__':main()
