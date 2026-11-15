"""Bundle code and the previously accepted small receipts for the transfer run."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE=Path(__file__).resolve().parent
RUNS=HERE.parent
REF=RUNS/'unified_reference_bank_k8192_v1_20261113'
ART=RUNS/'p4_tabm_acceptance_v1_20261111'
CAT=RUNS/'baseline_author_defaults_v1_20261108'
SLAD=RUNS/'baseline_slad_eval_repair_v1_20261108'
SAME=RUNS/'same_bank_context_v6_20261106'
REC=RUNS/'same_information_recalibration_v1_20261113'


def sha(x):
    return hashlib.sha256(x).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def json_bytes(x):
    return (json.dumps(x,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()


def build():
    data=read(REF/'.private/Q12_PROBE.json')['head_assets']
    old_eval=data[str(CAT.name+'/EVALUATION_INPUTS.json')]
    cat_eval=data[str(CAT.name+'/evaluate_CatBoost_27_RESULT.json')]
    slad_eval=read(SLAD/'EVALUATE_RESULT.json')
    assert old_eval==read(SLAD/'EVALUATION_INPUTS.json')
    assert cat_eval['scores']==read(CAT/'incident_slad_evaluation/evaluate_CatBoost_27_RESULT.json')['scores']
    assert cat_eval['metrics_sha256']==sha((CAT/'CatBoost_METRICS.json').read_bytes())
    assert slad_eval['metrics_sha256']==sha((SLAD/'SLAD_METRICS.json').read_bytes())
    assert cat_eval['status']==slad_eval['status']=='PASS'
    geometry=read(SAME/'DIAGNOSE_RESULT.json')['pools']
    bank=read(ART/'controls/REFERENCE_BANKS.json')
    for pool,d in geometry.items():
        assert d['reference_rows']==bank[pool]['full_bank']['rows']
        assert d['reference_uid_sha256']==bank[pool]['full_bank']['uid_sha256']
    tabm=read(ART/'tabm_p4/VERIFICATION.json')
    assert tabm['status']=='PASS' and not tabm['new_forward'] and not tabm['clipping']
    source=read(RUNS/'baseline_training_readiness_v6_20261107/SOURCE_RESULT.json')
    fit=read(ART/'tabm_p3/SOURCE_FIT_IDENTITY.json')
    assert source['status']==fit['status']=='PASS' and source['full_fit_rows']==fit['rows']==617908
    assert source['sha256']['FIT_X.npy']==fit['fit_x_sha256']
    config=dict(query=read(ART/'controls/QUERY_ASSETS.json'),geometry={
         pool:d['artifact'] for pool,d in geometry.items()},bank=bank,
         source={k:source[k] for k in ('full_fit_rows','normal_fit_rows','feature_count','sha256')},
         source_weights=fit,TabM=tabm,CatBoost=cat_eval,SLAD=slad_eval,
         old_evaluation=old_eval,slad_reload=read(SLAD/'CLEAN_PREDICTOR_GATE.json'))
    files={'HEAD_ASSETS.json':json_bytes(config)}
    for path in (HERE/'worker.py',HERE/'launch.py',HERE/'run.slurm',
                 REC/'analysis_core.py',REC/'common_round1.py'):
        files[path.name]=path.read_bytes().replace(b'\r\n',b'\n')
    for name,path in (
        ('CatBoost_METRICS.json',CAT/'CatBoost_METRICS.json'),
        ('SLAD_METRICS.json',SLAD/'SLAD_METRICS.json'),
        ('TABM_METRICS.json',ART/'tabm_p4/METRICS.json')):
        value=read(path)
        files[name]=json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
    for name,value in files.items():
        if name.endswith('.py'):
            compile(value,name,'exec')
    manifest=json_bytes(dict(run=HERE.name,files={name:sha(v) for name,v in sorted(files.items())}))
    files['PACKAGE_MANIFEST.json']=manifest
    path=REF/'.private/heads_package.tar.gz'
    with path.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as ar:
        for name,value in sorted(files.items()):
            item=tarfile.TarInfo(name);item.size=len(value);item.mode=0o700 if name.endswith('.slurm') else 0o600
            ar.addfile(item,io.BytesIO(value))
    (HERE/'HEAD_ASSETS.json').write_bytes(files['HEAD_ASSETS.json'])
    (HERE/'PACKAGE_MANIFEST.json').write_bytes(manifest)
    print('Head transfer package',len(files),path.stat().st_size,sha(manifest))


if __name__=='__main__':
    build()
