"""Generated regression suite then real frozen-head replay, no training."""
import json,sys,time,traceback,unittest
from pathlib import Path
ROOT=Path('/srv/paper04/onboarding_new_lineage_20261022_v1')
OUT=Path('/srv/paper04/onboarding_validation_20261022_v1')
sys.path.insert(0,str(ROOT))
import onboarding_service as service
def main():
    OUT.mkdir(exist_ok=False)
    service.write(OUT/'status.json',dict(status='RUNNING',stage='REGRESSION_TESTS',updated_epoch=time.time()))
    cfg=service.load();adapter,lc,m,design,original,plan,captures=service.bindings(cfg)
    import test_constrained_onboarding_integration_v1 as integ
    integ.PROTOCOL=ROOT/'frozen_onboarding/protocol.json'
    import test_onboarding_engineering_v2 as eng
    eng.PROTOCOL=integ.PROTOCOL
    names=['test_new_onboarding','test_constrained_onboarding_core_v1','test_constrained_onboarding_reference_v1','test_onboarding_engineering_v2','test_onboarding_delivery_v1']
    suite=unittest.defaultTestLoader.loadTestsFromNames(names)
    with (OUT/'tests.log').open('x') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    lc.require(result.wasSuccessful(),'REGRESSION_TESTS_FAILED')
    service.write(OUT/'tests.json',dict(status='PASS',tests=result.testsRun,code_manifest_sha256=lc.sha(ROOT/'code_manifest.json')))
    progress=service.ReplayProgress(OUT/'status.json');progress.tick(0,0)
    bundle=adapter.prepare(cfg,progress)
    m['constrained_onboarding_runner_v2']._validate_bundle(bundle,lc.read(ROOT/'frozen_onboarding/protocol.json'))
    service.write(OUT/'replay_proof.json',bundle['replay_evidence'])
    service.write(OUT/'status.json',dict(status='PASS',stage='REAL_HEAD_REPLAY_PASSED',tests=result.testsRun,
        code_manifest_sha256=lc.sha(ROOT/'code_manifest.json'),replay_proof_sha256=lc.sha(OUT/'replay_proof.json'),updated_epoch=time.time()))
if __name__=='__main__':
    try:main()
    except BaseException as exc:
        if OUT.is_dir():service.write(OUT/'status.json',dict(status='FAILED',error=repr(exc),traceback=traceback.format_exc(),updated_epoch=time.time()))
        raise
