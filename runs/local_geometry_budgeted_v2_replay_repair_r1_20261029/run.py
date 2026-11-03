"""Explicit check/source/target entry. Default check performs no new inference or distances."""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '4'
import argparse
from pathlib import Path

from lg.common import PACKAGE, ROOT, SPEC_SHA, require
from lg.runtime import StageRuntime, verify_package, verify_predecessor


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('check', 'source', 'target'), nargs='?', default='check')
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--output', type=Path)
    p.add_argument('--source-result', type=Path)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    require((args.stage == 'target') == (args.source_result is not None), 'SOURCE_RESULT_FOR_TARGET_ONLY')
    root = args.root.resolve()
    output = (args.output or PACKAGE/'outputs'/args.stage).resolve()
    require(output.is_relative_to(PACKAGE/'outputs'), 'OUTPUT_MUST_BE_NEW_PACKAGE_OUTPUTS')
    verify_package(root)
    if args.stage == 'target':
        verify_predecessor(args.source_result)
    with StageRuntime(args.stage, output, root=root) as runtime:
        if args.stage == 'check':
            from lg.source import preflight
            result = preflight(root)
            result.update(status='CHECK_PASS', scientific_status='NOT_EVALUATED', spec_sha256=SPEC_SHA,
                          new_head_forwards=0, distances=0, training=0, target_evaluations=0)
        elif args.stage == 'source':
            from lg.source import run_source
            result = run_source(root, output, runtime)
        else:
            from lg.target import run_target
            result = run_target(root, output, runtime, args.source_result)
        runtime.finish(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
