"""Selected modern-head generated checks from the installed sealed package."""
import argparse
import importlib
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--root',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); root=Path(args.root).resolve(); out=Path(args.output).resolve()
    if Path(__file__).resolve().parent!=root/'repo/ood': raise RuntimeError('TEST_INSTALLED_CODE_REQUIRED')
    sys.dont_write_bytecode=True; os.environ['MODERN_TEST_ROOT']=str(root)
    import continuous_common_v3 as c
    c.verify(root,exact=False); out.mkdir(parents=True,exist_ok=False)
    selections={
        'test_modern_head_revision_train_v1':None,
        'test_modern_head_revision_replay_v1':None,
        'test_modern_head_revision_runner_v1':None,
        'test_modern_head_runner_v1':None,
        'test_modern_head_models_v1':[
            'EndpointTests.test_all_families_train_save_reload_same_scores',
            'EndpointTests.test_adoption_requires_replay_proof_and_preserves_head_bytes'],
        'test_modern_head_evaluate_v1':[
            'ReplayAndOnboardingTests','OfficialMetricTests',
            'CalibrationTests.test_scope_and_gates_cannot_be_silently_reduced',
            'EndToEndEvaluationTests'],
    }
    records={}
    for name,selected in selections.items():
        module=importlib.import_module(name)
        if Path(module.__file__).resolve().parent!=root/'repo/ood': raise RuntimeError('TEST_IMPORT_ESCAPE')
        stream=io.StringIO(); begin=time.monotonic()
        suite=(unittest.defaultTestLoader.loadTestsFromModule(module) if selected is None else
               unittest.defaultTestLoader.loadTestsFromNames(selected,module))
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        log=out/(name+'.log'); log.write_text(stream.getvalue(),encoding='utf-8')
        records[name]=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
                           success=result.wasSuccessful() and not result.skipped,seconds=time.monotonic()-begin,
                           selected_tests=selected,log=log.name,sha256=c.sha(log))
        print(name,json.dumps(records[name]),flush=True)
        if not result.wasSuccessful(): print(stream.getvalue(),flush=True)
    summary=dict(status='PASS' if all(v['success'] for v in records.values()) else 'FAIL',tests=records,
                 total_tests=sum(v['tests'] for v in records.values()),package_seal_sha256=c.sha(root/'SHA256SUMS'),
                 validation_scope='v1r1 changed paths and selected regressions; not all inherited v1 tests',
                 real_training=False,real_pcap_decode=False,target_scoring=False)
    c.write(out/'result.json',summary); c.verify(root,exact=False)
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__': sys.exit(main())
