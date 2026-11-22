"""Reuse the accepted front end and run the immutable three v12 heads."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent
PILOT=HERE.parent/"p4_login_pilot_v1_20261121"
sys.path.insert(0,str(PILOT))
from audit import identity, join, read, save, sha
from feature_witness import TON, FROZEN, NORM, e3_batch, frame_inputs, runtime

import numpy as np

HEADS=(27,127,227)
CONTEXT=PILOT/".private/source_context_normalizer.npz"


@contextmanager
def sealed_runtime():
    stage=HERE/".private"
    stage.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=stage) as d:
        package=Path(d)
        with tarfile.open(TON/".private/package.tar.gz") as arc:
            for entry in arc.getmembers():
                assert entry.isfile() and entry.name==Path(entry.name).name
                (package/entry.name).write_bytes(arc.extractfile(entry).read())
        assert identity(package/"PACKAGE_MANIFEST.json")["sha256"]==read(TON/"received/ACCEPTANCE.json")["package_sha256"]
        yield runtime(package)


def calibration(pins):
    context=pins["context_normalizer"]["sha256"]
    assert identity(CONTEXT)["sha256"]==context
    with np.load(NORM,allow_pickle=False) as a, np.load(CONTEXT,allow_pickle=False) as b:
        mean,sd=a["mean"],a["scale"]
        ctx_mean,ctx_sd=b["mean"],b["scale"]
    assert mean.shape==sd.shape==(768,) and ctx_mean.shape==ctx_sd.shape==(8,)
    assert np.isfinite([*mean,*sd,*ctx_mean,*ctx_sd]).all() and (sd>0).all() and (ctx_sd>0).all()
    return mean,sd,ctx_mean,ctx_sd


def inputs790(z,q,x,norm):
    a,b,c,d=norm
    zz=((z.astype(np.float64)-a)/b).astype(np.float32)
    cc=((np.log1p(x)-c)/d).astype(np.float32)
    result=np.column_stack((zz,q,cc)).astype("<f4")
    assert result.shape==(len(z),790) and np.isfinite(result).all()
    return result


def models(assets):
    import torch
    from torch import nn

    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    frozen=read(TON/"FROZEN.json")["extra_pins"]
    nets=[]
    for seed in HEADS:
        path=assets/f"head_{seed}.npz"
        assert identity(path)["sha256"]==frozen[f"head_{seed}"]["sha256"]
        net=nn.Sequential(nn.Linear(790,128),nn.ReLU(),nn.Linear(128,1))
        with np.load(path,allow_pickle=False) as state:
            net.load_state_dict({k:torch.from_numpy(state[k].copy()) for k in state.files})
        nets.append(net.eval().requires_grad_(False))
    return nets


def four(seed_values):
    f=seed_values.astype(np.float64)
    return np.column_stack((f,f.mean(axis=1,dtype=np.float64)))


def scores(nets,values):
    import torch

    with torch.inference_mode():
        cols = [net(torch.from_numpy(values)).flatten().numpy() for net in nets]
    a=four(np.column_stack(cols))
    assert a.shape==(len(values),4) and np.isfinite(a).all()
    return a


def adjusted(raw,support,guard,method):
    assert method["p"]==4 and method["lambda_value"]==.25
    s=np.where(guard,0.,1.-np.power(1.-support,4.))
    seed=raw[:,:3] - (method["lambda_value"]*np.array(method["scales"]))[None,:]*s[:,None]
    return four(seed)


def digest_order(uid):
    return sha("".join(str(u)+"\n" for u in uid).encode("ascii"))


def verify_source(pilot):
    receipt=read(pilot/"ACCEPTANCE.json")
    manifest={}
    for row in (pilot/"SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected,name=row.split("  ",1)
        assert (pilot/name).parent==pilot and identity(pilot/name)["sha256"]==expected
        manifest[name]=expected
    assert receipt["status"]=="PASS" and receipt["checks"]["aligned_requests"]==150
    return receipt,manifest


def quick(out,pilot,assets,cfg,pins):
    saved,source=verify_source(pilot)
    trace=read(pilot/"CAPTURE.json")
    report, pairs, fields=join(pilot,trace)
    assert report["status"]=="PASS" and json.loads(json.dumps(report["checks"]))==saved["checks"]
    anchors={r["frame"]:r for r in pairs if r["aligned"]}
    roster=frame_inputs(fields,trace,report["pcap"]["sha256"],anchors)
    e3,encoder,batches=e3_batch(roster,pins)
    q=np.stack([r[-2] for r in roster]).astype(np.float32)
    x=np.asarray([r[-1] for r in roster],dtype=np.float64)
    normal=calibration(pins)
    pilot_x=inputs790(e3,q,x,normal)
    assert sha(pilot_x.tobytes())==saved["features"]["frozen_790_input_sha256"]
    uid=np.asarray([r[0] for r in roster])
    assert digest_order(uid)==saved["checks"]["request_uid_order_sha256"]
    h=np.asarray([anchors[r[1]]["handshakes_60s"] for r in roster])
    method=cfg["method"]
    cfg_path=FROZEN/"CONFIG.json"
    thresh=np.array(method["cuts"])
    nets=models(assets)
    logits=scores(nets,pilot_x)
    assert np.array_equal(logits,scores(nets,pilot_x))
    raw=logits>thresh
    before=adjusted(logits,np.zeros(len(h)),np.zeros(len(h),bool),method)>thresh
    assert np.array_equal(before,raw)
    rp=out/"PILOT_SCORES.npz"
    np.savez(rp,uid=uid,input790=pilot_x,handshakes=h,score=logits,cuts=thresh,raw=raw,v12=before)
    cert=read(assets/"ACCEPTANCE.json")
    with np.load(assets/"ATTACK_FIXTURE.npz",allow_pickle=False) as a:
        assert len(a["uid"])==cert["rows"] and digest_order(a["uid"])==cert["uid_order_sha256"]
        assert (a["label"]==1).all()
        attack_x=inputs790(a["z"],a["q"],a["physical"],normal)
        score=scores(nets,attack_x)
        diff=float(np.max(np.abs(score-a["scores"])))
        assert diff<=5e-4,("FROZEN_HEAD_LOGIT_ERROR",diff)
        raw_same=np.array_equal(score>thresh,a["expected_raw"])
        ccnr_same=np.array_equal(adjusted(score,a["support"],a["guard"],method)>thresh,a["expected_v12"])
        assert raw_same and ccnr_same,"SEALED_ATTACK_DECISIONS"
        attack=dict(rows=len(score),mode=cert["scope"],strata=cert["selected"],observed_score_abs_diff_max=diff,
                    input_shape=list(attack_x.shape),uid_order_sha256=cert["uid_order_sha256"],
                    logits_assertion_tolerance=.0005,raw_disagreements=0,v12_disagreements=0,
                    archive_receipt=identity(assets/"ACCEPTANCE.json"),
                    raw_alarms=a["expected_raw"].sum(0).tolist(),v12_alarms=a["expected_v12"].sum(0).tolist())
    info=dict(status="PASS", heads=list(HEADS), threshold=method["cuts"], config=identity(cfg_path),
              pilot=dict(rows=len(h),pcap=source["login.pcap"],input_sha256=sha(pilot_x.tobytes()),
                         input_shape=list(pilot_x.shape), UID_order=digest_order(uid), exact_handshakes=len(h),
                         handshake_range=[int(h.min()),int(h.max())],raw_alarms=raw.sum(0).tolist(),
                         repeated_score_exact=True, correction="two_hour_bank_unavailable", scores=identity(rp)),
              archived_attack=attack,encoder=encoder,physical_batches=batches,
              hardware="local CPU",normalizers={"context":identity(CONTEXT),"e3":identity(NORM)})
    save(out/"QUICK_CHECK.json",info)
    return trace,report,pairs,fields,info


if __name__=="__main__":
    target,pilot,assets=map(Path,sys.argv[1:])
    with sealed_runtime() as (cfg,pins):
        _,_,_,_,info=quick(target,pilot,assets,cfg,pins)
    print("QUICK_CHECK",info["status"],info["pilot"]["rows"],info["archived_attack"]["rows"],flush=True)
