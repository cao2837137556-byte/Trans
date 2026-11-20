"""Reproduce the 186137 module collision and exercise the repaired score handoff locally."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np
import compare
from auxiliary import sha

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
PROBE = HERE / ".private/import_probe"


def local_environment(project):
    sys.path.insert(0,str(PROBE/"ton"))
    from frozen_env import setup,store
    _, freeze,cfg,geometry = setup(project,local_runtime=PROBE/"old")
    return store(project,freeze),cfg,geometry


def local_model(store,cfg):
    import torch
    pins = {n:store.get("model:"+n).resolve() for n in cfg["model_modules"]}
    sys.path.insert(0,str(pins["context_core"].parent))
    try:
        import context_core as core
    finally:
        sys.path.pop(0)
    assert all(Path(sys.modules[n].__file__).resolve()==p for n,p in pins.items())
    nets=[core.classifier(seed,790).eval() for seed in (27,127,227)]
    return core,nets,(np.zeros(768),np.ones(768)),(np.zeros(8),np.ones(8))


def regression():
    attempt=HERE/"attempts/186137/ORIGINAL_FAILURE.json"
    assert "FOREIGN_PRODUCTION_MODULE:legacy_qref_common_v1" in json.loads(attempt.read_bytes())["stderr"]
    assert subprocess.run([sys.executable,"-B",__file__,"old"],check=True).returncode==0
    st,cfg,geometry=local_environment(PROJECT)
    from reference_inputs import normalized_context
    from paired_replay import ref_bank
    from vendor import p4_worker
    assert Path(sys.modules["legacy_qref_common_v1"].__file__).resolve().parent==(PROBE/"old/vendor").resolve()
    rng=np.random.default_rng(186137)
    ids=[f"{i:064x}" for i in (7,2,99,1)]
    z=rng.normal(size=(4,768)).astype(np.float32)
    q=rng.uniform(size=(4,14)).astype(np.float32)
    x=rng.uniform(size=(4,8))
    with tempfile.TemporaryDirectory(dir=HERE/".private") as tmp:
        out=Path(tmp)
        check=compare.Controls(PROJECT,out,st,cfg,geometry,None,None,np.asarray(cfg["method"]["cuts"]),True)
        def local_child(args,output,name):
            cmd=[sys.executable,"-B",__file__,"head",*args[-4:]]
            subprocess.run(cmd,check=True)
        with patch("compute.run_child",side_effect=local_child):
            raw=compare.raw_pair(check,ids,z,q,x)
        assert np.array_equal(*raw) and raw[0].shape==(4,4)
        decisions,old,after=compare.paired(check,raw,q,np.array([0,.05,.3,.9]))
        assert np.isfinite(after).all() and all(np.array_equal(a,b) for _,a,b in decisions)
    receipt=dict(old_failure_reproduced=True,original_job="186137",new_geometry_and_model_processes=True,
                 query_uid_order_roundtrip=True,local_fixture_rows=len(ids),model_module_file_pins_checked=True,
                 archived_models_scored=False,local_smoke="untrained fixture heads; actual archived heads checked on compute node",
                 old_stderr_receipt_sha256=sha(attempt))
    (HERE/"IMPORT_REPAIR_LOCAL.json").write_bytes((json.dumps(receipt,indent=2)+"\n").encode())
    print("PASS: reproduced old error; isolated inference and correction passed")


if __name__=="__main__":
    if sys.argv[1:]==["old"]:
        st,cfg,_=local_environment(PROJECT)
        local_model(st,cfg)
        try:
            import reference_inputs
        except ImportError as exc:
            assert str(exc)=="FOREIGN_PRODUCTION_MODULE:legacy_qref_common_v1",str(exc)
        else:
            raise AssertionError("The old import collision was not reproduced")
    elif sys.argv[1:2]==["head"]:
        project,out,folder=map(Path,sys.argv[2:5])
        st,cfg,geom=local_environment(project)
        import reference_assets
        with patch.object(compare,"environment",return_value=(st,cfg,geom)),patch.object(reference_assets,"model_setup",side_effect=local_model):
            compare.head_forward(project,out,folder,sys.argv[5]=="baseline")
    else:
        regression()
