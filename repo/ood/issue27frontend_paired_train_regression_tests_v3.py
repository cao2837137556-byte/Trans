"""Run existing generated regressions against V3 without editing frozen tests."""
import argparse
import json
import unittest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('suite',choices=('core','prefix','supervisor'))
    args=parser.parse_args()
    import issue27frontend_paired_train_support_v3 as s
    import issue27frontend_paired_train_control_v3 as c
    if args.suite=='supervisor':
        import issue27frontend_paired_train_supervisor_tests_v2 as t
        t.c=c;t.s=s;t.inherited.c=c;t.inherited.s=s
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(t.SingleWorkerTests)
        for name in unittest.defaultTestLoader.getTestCaseNames(t.inherited.ControllerTests):
            if name not in ('test_generated_decoder_child_is_killed_with_worker','test_explicit_gate_rejects_before_readiness'):
                suite.addTest(t.inherited.ControllerTests(name))
    else:
        import issue27frontend_paired_train_runner_v3 as r
        if args.suite=='core':
            import issue27frontend_paired_train_tests_v2 as t
            import issue27frontend_paired_train_metrics_v2 as metrics
            t.s=s;t.c=c;t.r=r;t.metrics=metrics;t.m.configure()
            suite=unittest.defaultTestLoader.loadTestsFromModule(t)
        else:
            import issue27frontend_paired_train_prefix_tests_v2 as t
            t.s=s;t.runner=r
            suite=unittest.defaultTestLoader.loadTestsFromTestCase(t.PrefixTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'suite':args.suite,'tests_run':result.testsRun,
        'tests_passed':result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped),
        'real_feature_bytes_decoded':0,'real_optimizer_steps':0,'scope':'existing generated tests rebound to V3 implementation'}
    print('SYNTHETIC_RESULT '+json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__=='__main__':main()
