"""Source retry entry requiring the recorded 179460 environment before forwards."""
import argparse
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '4'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import json
import platform

from lg.common import PACKAGE, ROOT, read_json, require, sha
from lg.runtime import code_seal, verify_package


def environment():
    import numpy as np
    import torch
    return dict(python=platform.python_version(), numpy=np.__version__,
                torch=torch.__version__, system=platform.system())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-env', action='store_true', help='Import/version check only, no model or input arrays')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    require(args.check_env != (args.output is not None), 'CHOOSE_CHECK_ENV_OR_SOURCE_OUTPUT')
    current = environment()
    expected = dict(python='3.11.11', numpy='1.26.4', torch='2.5.1', system='Linux')
    print(json.dumps(dict(current=current, expected=expected, new_head_forwards=0)), flush=True)
    require(all(str(current[k]).split('+')[0] == v for k, v in expected.items()), 'HISTORICAL_SOURCE_ENVIRONMENT_MISMATCH')
    if args.check_env:
        return 0
    receipt = read_json(PACKAGE/'IMPLEMENTATION_RECEIPT.json')
    require(receipt['code_sha256'] == code_seal(), 'REPAIR_CODE_CHANGED')
    for rel, digest in receipt['files_sha256'].items():
        require(sha(PACKAGE/rel) == digest, 'REPAIR_FILE_CHANGED:' + rel)
    verify_package(ROOT)
    from run import main as run_stage
    return run_stage(['source', '--output', args.output])


if __name__ == '__main__':
    raise SystemExit(main())
