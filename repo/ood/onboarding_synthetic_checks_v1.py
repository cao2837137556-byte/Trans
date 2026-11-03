"""Packaged generated-data checks; real tokenizer is mandatory on the target."""
import argparse
import importlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import types
import unittest


def remapped_suite(code):
    suite = unittest.TestSuite()
    for stem in ('core', 'integration', 'query_tail_adapter'):
        path = code/('test_constrained_onboarding_'+stem+'_v1.py')
        source = path.read_text(encoding='utf-8')
        for name in ('core', 'runner', 'query_tail_adapter'):
            source = re.sub(r'\bconstrained_onboarding_'+name+'_v1\b', 'constrained_onboarding_'+name+'_v2', source)
        module = types.ModuleType('packaged_onboarding_remap_'+stem); module.__file__ = str(path)
        sys.modules[module.__name__] = module
        exec(compile(source, str(path)+' [v2 imports]', 'exec'), module.__dict__)
        if hasattr(module, 'PROTOCOL'):
            module.PROTOCOL = code.parents[1]/'protocol.json'
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    return suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--local-without-tokenizer',action='store_true')
    args = parser.parse_args()
    root = Path(args.root).resolve(); out = Path(args.output).resolve(); code = root/'repo/ood'
    if Path(__file__).resolve().parent != code:
        raise RuntimeError('TEST_INSTALLED_CODE_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(code)); sys.dont_write_bytecode = True
    from continuous_common_v3 import verify, sha
    verify(root,exact=False)
    from onboarding_delivery_v1 import load_contract
    load_contract(root)
    os.environ['CONTINUOUS_TEST_ROOT'] = str(root)
    # Existing generated fixtures use the historical workspace protocol path.
    # Bind only their test constant to the identical sealed package copy.
    importlib.import_module('test_constrained_onboarding_integration_v1').PROTOCOL = root/'protocol.json'
    modules = ('test_constrained_onboarding_reference_v1','test_onboarding_engineering_v2',
               'test_engineering_state_storage_v1','test_engineering_progress_v1',
               'test_onboarding_delivery_io_v1','test_onboarding_delivery_v1')
    suites = [('v2_scientific_compatibility',remapped_suite(code))]
    for name in modules:
        loaded = importlib.import_module(name)
        if Path(loaded.__file__).resolve().parent != code:
            raise RuntimeError('TEST_IMPORT_OUTSIDE_PACKAGE:'+name)
        suites.append((name,unittest.defaultTestLoader.loadTestsFromModule(loaded)))
    if not args.local_without_tokenizer:
        suites.append(('actual_tokenizer',unittest.defaultTestLoader.loadTestsFromName('test_continuous_repair_v3.ActualTokenizer')))
    records = {}
    for name,suite in suites:
        stream = io.StringIO(); begin = time.perf_counter()
        result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        log = out/(name+'.log');log.write_text(stream.getvalue(),encoding='utf-8')
        records[name] = dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
            skipped=len(result.skipped),success=result.wasSuccessful() and not result.skipped,
            seconds=time.perf_counter()-begin,log=log.name,sha256=sha(log))
        print(name,json.dumps(records[name]),flush=True)
        if not result.wasSuccessful(): print(stream.getvalue(),flush=True)
    summary = dict(status='PASS' if all(r['success'] for r in records.values()) else 'FAIL',
        tests=records, total_tests=sum(r['tests'] for r in records.values()),
        actual_tokenizer='NOT_RUN_LOCAL_DEPENDENCY_UNAVAILABLE' if args.local_without_tokenizer else 'INCLUDED',
        package_seal_sha256=sha(root/'SHA256SUMS'),model_training=False,real_pcap_decode=False,real_e3=False)
    (out/'result.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    verify(root,exact=False)
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
