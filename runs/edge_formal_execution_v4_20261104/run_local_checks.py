"""Reproducible local checks and receipts, with no model or remote execution."""
import json
from pathlib import Path
import platform
import time
import unittest

from checkpoint import atomic_json, require, sha

HERE = Path(__file__).resolve().parent
SUITES = {
    'test_adopt_roles': 'ROLE_ADOPTION_TEST_RECEIPT.json',
    'test_replay_resume': 'REPLAY_RESUME_TEST_RECEIPT.json',
    'test_review_authorization': 'REVIEW_AUTHORIZATION_TEST_RECEIPT.json',
    'test_preflight_contract': 'PREFLIGHT_CONTRACT_TEST_RECEIPT.json',
    'test_checkpoint': 'CHECKPOINT_TEST_RECEIPT.json',
    'test_streaming': 'STREAMING_TEST_RECEIPT.json',
    'test_reporting': 'STATISTICS_TEST_RECEIPT.json',
    'test_budget': 'BUDGET_TEST_RECEIPT.json',
    'test_engineering_gate': 'ENGINEERING_GATE_TEST_RECEIPT.json',
    'test_repairs': 'REPAIR_REGRESSION_RECEIPT.json',
    'test_progress_io': 'PROGRESS_IO_TEST_RECEIPT.json',
    'test_v3_integration': 'V3_INTEGRATION_TEST_RECEIPT.json',
}


def ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()


def main():
    started = time.monotonic()
    sources = {p.name: sha(p) for p in sorted(HERE.glob('*.py'))}
    results = {}
    for module, name in SUITES.items():
        suite = unittest.defaultTestLoader.loadTestsFromName(module)
        tests = list(ids(suite))
        before = time.monotonic()
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        receipt = dict(status='PASS' if result.wasSuccessful() else 'FAIL',
            tests=result.testsRun, test_ids=tests, failures=len(result.failures),
            errors=len(result.errors), skipped=len(result.skipped), seconds=time.monotonic()-before,
            source_sha256=sources, platform=platform.platform(), python=platform.python_version(),
            frozen_model_calls=0, cloud_jobs_submitted=0, external_quality_computed=False,
            linux_frozen_runtime_acceptance='PENDING_NOT_EXECUTED')
        atomic_json(HERE/name, receipt)
        results[module] = dict(status=receipt['status'], tests=result.testsRun,
                              path=name, sha256=sha(HERE/name))
    require(sources == {p.name: sha(p) for p in sorted(HERE.glob('*.py'))}, 'SOURCE_CHANGED_DURING_TESTS')
    value = dict(schema='EDGE_V3_LOCAL_REGRESSION',
        status='PASS' if all(r['status']=='PASS' for r in results.values()) else 'FAIL',
        tests=sum(r['tests'] for r in results.values()), suites=results, source_sha256=sources,
        seconds=time.monotonic()-started, frozen_model_calls=0, cloud_jobs_submitted=0,
        external_quality_computed=False, linux_gate='PENDING_NOT_EXECUTED')
    atomic_json(HERE/'LOCAL_REGRESSION_RECEIPT.json', value)
    print(json.dumps({k:v for k,v in value.items() if k not in ('source_sha256','suites')}))
    require(value['status']=='PASS', 'LOCAL_REGRESSION_FAILED')


if __name__ == '__main__':
    main()
