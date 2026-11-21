"""Fit no parameters. Read the original CIC roles, weights, feature arrays and both sealed heads."""
import hashlib
import os
import sys
from pathlib import Path
import time
import numpy as np
from shared import HERE, PARENT, MODELS, HEADS, read, write, sha, uid_sha


def original_calibration(training, seed, spec, cal_order, uid_hash):
    tag = "FUSION790_" + seed
    head_receipt = training / f"TRAIN_{tag}_RESULT.json"
    if sha(head_receipt) != spec["v12_training_receipts"][seed]:
        raise ValueError(f"Sealed v12 training receipt changed for seed {seed}")
    original = read(head_receipt)
    assert original["status"] == "PASS" and not original["runtime_gate_only"]
    assert original["seed"] == int(seed) and original["arm"] == "FUSION790"
    assert original["head_sha256"] == spec["heads"]["v12"][seed]
    folder = training / "heads" / tag / "calibration"
    cert = read(folder / "RESULT.json")
    assert cert == original["calibration"] and cert["normal_rows"] == 33147
    assert cert["cal_uid_sha256"] == uid_hash(cal_order)
    assert cert["scale_source"] == "FIT" and cert["threshold_source"] == "CAL_NORMAL"
    for role in ("fit", "cal"):
        if sha(folder / f"{role}_logits.npy") != cert["logits_sha256"][role]:
            raise ValueError(f"Sealed v12 {role.upper()} scores changed for seed {seed}")
    return folder, cert


def progress(out, model, seed):
    write(out / "PROGRESS.json", dict(
        phase="preflight", job=os.environ["SLURM_JOB_ID"], updated_unix=time.time(),
        description=f"{model} 种子 {seed} 的 CIC 源跨度与阈值已核对",
    ))


def run(project, out):
    parent=project/"runs"/PARENT
    sys.path.insert(0,str(parent/"package"))
    from train_candidate import source
    worker,data=source(project)
    import torch
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    spec=read(HERE/"CONTRACT.json")
    freeze=read(parent/"CANDIDATE_FREEZE.json")
    assert sha(parent/"formal/fit_meta.npz")==freeze["calibration_sha256"]
    fit=data["fit"]
    all_calrows = [data["rows"][int(i)] for i in data["cal"]]
    is_normal = np.array([r["label"] == 0 for r in all_calrows])
    all_calids = [r["uid"] for r in all_calrows]
    cal = data["cal"][is_normal]
    nr=[data["rows"][int(i)] for i in cal]
    ids=[data["rows"][int(i)]["uid"] for i in fit]
    calids=[r["uid"] for r in nr]
    assert len(fit)==617908 and len(cal)==33147 and not set(ids).intersection(calids)
    with np.load(parent/"formal/fit_meta.npz",allow_pickle=False) as a:
        assert int(a["n_cic"])==len(fit) and np.array_equal(a["uid"][:len(fit)],ids)
        assert np.array_equal(a["cic_w"],data["w"]) and np.array_equal(a["cal_uid"],calids)
        assert np.array_equal(a["cal_w"],worker.k.class_weights(nr))
    training = project / "runs/device_context_head_training_v2_20261105"
    res={}
    for model in MODELS:
        cuts=np.array(spec["cuts"][model])
        cal_vectors=[]
        qs=[]
        for i,seed in enumerate(HEADS[:3]):
            ck=training/"heads"/("FUSION790_"+seed)/"train/head.npz" if model=="v12" else parent/"formal"/("head_"+seed+".npz")
            assert sha(ck)==spec["heads"][model][seed]
            net=worker.k.classifier(int(seed),790)
            with np.load(ck,allow_pickle=False) as a:
                net.load_state_dict({key:torch.from_numpy(a[key].copy()) for key in a.files})
            net.eval().requires_grad_(False)
            def score(ix):
                return worker.k.scores(net,data["values"],data["q"],ix,data["norm"],790)
            if model=="v12":
                folder, cert = original_calibration(training, seed, spec, all_calids, worker.k.c.uid_sha)
                assert cert["cut"] == cuts[i]
                f=np.load(folder/"fit_logits.npy",mmap_mode="r")
                full=np.load(folder/"cal_logits.npy",mmap_mode="r")
                assert len(f)==len(fit) and len(full)==len(data["cal"])
                np.testing.assert_allclose(score(fit[:1024]),f[:1024],atol=2e-4,rtol=0)
                c=full[is_normal]
            else:
                f=score(fit)
                c=np.load(parent/"formal"/("cal_"+seed+".npy"))
                np.testing.assert_allclose(score(cal),c,rtol=0,atol=2e-4)
            q=[worker.onboarding.weighted_quantile(f,data["w"],v) for v in (.1,.5,.9)]
            assert q[2]>q[0] and worker.k.threshold(c,nr,.01)==cuts[i]
            if model=="v12": assert (q[0],q[2])==(cert["q10"],cert["q90"])
            qs.append(q);cal_vectors.append(c)
            progress(out,model,seed)
        vals=np.stack(cal_vectors,axis=1).astype(np.float64)
        original_mean = (worker.onboarding.ordered_ensemble(dict(zip((27,127,227),cal_vectors)))
                         if model == "v12" else vals.mean(axis=1))
        assert worker.k.threshold(original_mean,nr,.01)==cuts[3]
        span=np.subtract(np.asarray(qs)[:,2],np.asarray(qs)[:,0])
        if model == "v12": np.testing.assert_array_equal(span,spec["v12_fit_spans"])
        norm=((vals-cuts[:3])/span).mean(axis=1)
        t=worker.k.threshold(norm,nr,.01)
        w=worker.k.class_weights(nr)
        fpr=float(w[norm>t].sum())
        assert fpr<=.01+1e-13
        res[model]=dict(quantiles=qs,span=span.tolist(),cuts=cuts.tolist(),standard_cut=t,
                        standard_cal_fpr=fpr,original_cal_fpr=float(w[original_mean>cuts[3]].sum()))
    write(out/"SOURCE.json",dict(models=res,baseline=spec["base_scales"],baseline_origin="REFIT782 CIC FIT",
          fit=len(fit),cal=len(cal),
          fit_order=uid_sha(ids),cal_order=uid_sha(calids),fit_weight_sha256=hashlib.sha256(data["w"].tobytes()).hexdigest()))


if __name__=="__main__":
    run(*map(Path,sys.argv[1:3]))
