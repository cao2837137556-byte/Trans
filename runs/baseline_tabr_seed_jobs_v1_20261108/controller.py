"""Separate immutable-seed jobs, then afterok evaluation. No model change."""
import sys,os,subprocess,time,traceback,json
from pathlib import Path
import worker as w
p=w.p;HERE=w.HERE;PREVIOUS=HERE.parent/'baseline_remaining_three_v2_20261108'
assert Path(w.__file__).resolve()==Path(__file__).with_name('worker.py').resolve()

def submit(stage,dependencies=()):
    target=HERE/(stage+'_JOB.json')
    if target.exists():return p.read(target)['job_id']
    project=str(HERE.parents[1]);wall='1-00:00:00' if stage=='evaluate' else '7-00:00:00'
    script='#!/bin/bash\n#SBATCH --partition=gpu\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=8\n#SBATCH --mem=32768M\n#SBATCH --gres=gpu:nvidia_geforce_rtx_4090:1\n#SBATCH --time='+wall+'\n#SBATCH --no-requeue\n#SBATCH --job-name=tabr-'+stage+'\n#SBATCH --output='+str(HERE/(stage+'-%j.out'))+'\n#SBATCH --error='+str(HERE/(stage+'-%j.err'))+'\nset -euo pipefail\numask 077\nsource '+project+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+project+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+project+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1 CUBLAS_WORKSPACE_CONFIG=:4096:8\nexec '+sys.executable+' -X utf8 -B '+str(HERE/'controller.py')+' '+stage+'\n'
    path=HERE/(stage+'.slurm');path.write_text(script)
    args=['sbatch','--parsable']+(['--dependency=afterok:'+':'.join(dependencies)] if dependencies else [])+[str(path)]
    r=subprocess.run(args,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
    job=r.stdout.strip().split(';')[0];assert job.isdigit();p.write(stage+'_JOB.json',dict(job_id=job,stage=stage,cpu=8,memory_gib=32,gpu='RTX4090',wall_seconds=86400 if stage=='evaluate' else 604800,afterok=list(dependencies)));return job

def prepare():
    assert p.sha(HERE/'worker.py')==p.sha(PREVIOUS/'worker.py')
    assert p.sha(HERE/'CONFIG.json')==p.sha(PREVIOUS/'CONFIG.json')
    q=p.read(PREVIOUS/'TabR_QUALIFY.json');assert q['status']=='PASS' and q['fresh_process_resume_exact'] and q['full_epoch_rows']==617908 and q['all_candidates']
    assert q['gpu']=='NVIDIA GeForce RTX 4090'
    # The old safety estimate includes three seeds and evaluation. Applying its
    # third to each seed is conservative; evaluation receives its own day.
    per_seed=q['estimated_seconds']/3;assert per_seed<604800-7200
    eval_rows=sum(v['rows'] for v in p.read(PREVIOUS/'EVALUATION_INPUTS.json')['pools'].values())
    pilot=p.read(PREVIOUS/'PIPELINE_RESULT.json');pilot_rows=pilot['cal_normal_rows']+sum(pilot['target_rows'].values())
    evaluation=q['pilot_score_seconds']*eval_rows/pilot_rows*3*1.5+3600;assert evaluation<86400-3600
    p.progress('TABR_REPAIR_REAL_PIPELINE');p.write('PIPELINE_RESULT.json',p.pipeline())
    out=HERE/'artifacts/evaluation';out.mkdir(parents=True,exist_ok=True)
    spec=p.read(PREVIOUS/'EVALUATION_INPUTS.json')
    for pool,v in spec['pools'].items():
        for suffix,key in [('_X.npy','x_sha256'),('_ROWS.json','rows_sha256')]:
            a=PREVIOUS/'artifacts/evaluation'/(pool+suffix);assert p.sha(a)==v[key];(out/a.name).symlink_to(a.resolve())
        if pool!='EDGE':(out/(pool+'_VIEWS.npz')).symlink_to((PREVIOUS/'artifacts/evaluation'/(pool+'_VIEWS.npz')).resolve())
    p.write('EVALUATION_INPUTS.json',spec);split=p.read(PREVIOUS/'SPLIT_RESULT.json');mask=PREVIOUS/'artifacts/INNER_VALID.npy';assert p.sha(mask)==split['mask_sha256'];(HERE/'artifacts/INNER_VALID.npy').symlink_to(mask);p.write('SPLIT_RESULT.json',split)
    p.write('RESOURCE_RELEASE.json',dict(status='PASS',previous_qualification_sha256=p.sha(PREVIOUS/'TabR_QUALIFY.json'),estimated_per_seed_seconds=per_seed,estimated_evaluation_seconds=evaluation,method_unchanged=True,full_candidates=True))
    ids=[submit('seed-'+str(seed)) for seed in [27,127,227]];ev=submit('evaluate',ids)
    p.write('PREPARE_COMPLETE.json',dict(status='PASS',seed_jobs=ids,evaluation_job=ev))

def main(stage):
    os.environ['BASELINE_METHOD']=stage;w.init()
    if stage=='prepare':return prepare()
    if stage.startswith('seed-'):
        seed=int(stage.split('-')[1]);assert seed in [27,127,227]
        # Each process writes a separate progress filename, never one shared file.
        r=w.train('TabR',seed,'select');result=w.train('TabR',seed,'refit',r['best_epoch'])
        p.write(stage+'_COMPLETE.json',result)
    else:
        assert stage=='evaluate'
        for seed in [27,127,227]:assert p.read(HERE/('seed-'+str(seed)+'_COMPLETE.json'))['status']=='PASS'
        def boot():
            c=p.bootstrap();w.torch.set_num_threads(8);return c
        w.f.bootstrap=boot;w.f.predictor=w.predictor;p.write('TabR_EVALUATE.json',w.f.evaluate('TabR'));p.write('TabR_COMPLETE.json',dict(status='PASS',main_model_changed=False))

if __name__=='__main__':
    stage=sys.argv[1]
    try:main(stage)
    except Exception as e:p.HERE=HERE;p.write(stage+'_STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()));raise
