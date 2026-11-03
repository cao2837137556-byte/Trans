"""Generated integration harness, confined to a tempfile directory; not a real entry."""
import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
import issue27frontend_paired_train_support_v3 as real_support
import issue27frontend_paired_train_control_v3 as c


def bind(root):
    root=root.resolve()
    real_support.require(root.parent==Path(tempfile.gettempdir()).resolve() and
                         root.name.startswith('paired_generated_'),'FIXTURE_TEMP_ONLY')
    marker=real_support.read_json(root/'GENERATED_FIXTURE.json')
    real_support.require(marker['generated_only'] is True,'GENERATED_MARKER')
    scope=SimpleNamespace(**vars(real_support))
    scope.ROOT=root;scope.PACKAGE='package';scope.PREP='prepare';scope.REAL='train'
    scope.MEMBERSHIP='membership'
    scope.MEMBERSHIP_SHA=marker['membership_manifest_sha256']
    scope.PLAN_SHA=marker['plan_sha256']
    c.s=scope
    return scope


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--stage',choices=('prepare','train'),required=True)
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args();s=bind(args.root)
    output=s.ROOT/(s.PREP if args.stage=='prepare' else s.REAL)
    if args.worker:
        deadline=time.monotonic()+30
        while not (output/'worker_gate.json').exists():
            s.require(time.monotonic()<deadline,'FIXTURE_GATE_TIMEOUT');time.sleep(.01)
        gate=s.read_json(output/'worker_gate.json')
        s.require(gate['worker_pid']==os.getpid() and gate['parent_pid']==os.getppid(),'WORKER_GATE_IDENTITY')
        config=c.readiness(args.stage)
        from issue27frontend_paired_train_runner_v3 import worker
        import issue27frontend_paired_train_runner_v3 as r
        r.s=s
        worker(output,config,args.stage,gate['started']);return
    config=c.readiness(args.stage)
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'--root',str(s.ROOT),'--stage',args.stage,'--worker']
    # Production readiness, Windows supervisor, worker, and terminal validator
    # run unmocked. synthetic=False here exercises the same validation branch;
    # every path/byte/weight comes from the generated-only tempfile fixture.
    verdict=c.supervise(command,output,config,validator=c.validate_worker)
    print(s.canonical({'fixture':True,'verdict':verdict,'seal':s.sha_file(output/'SHA256SUMS')}).decode(),flush=True)


if __name__=='__main__':main()
