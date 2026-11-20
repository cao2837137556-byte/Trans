"""Train the independent FUSION790 candidate, keeping the control checkpoint read-only."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import torch

HERE = Path(__file__).resolve().parent


def training_weights(cic_w, cic_y, aux_y, groups, mix):
    w = np.zeros(len(cic_y) + len(aux_y), dtype=np.float64)
    aux = w[len(cic_y):]
    group_names = sorted(set(groups.tolist()))
    for label in (0,1):
        ix = np.flatnonzero(cic_y == label)
        for name in group_names:
            loc = np.flatnonzero((groups == name) & (aux_y == label))
            if not len(loc):
                raise ValueError("missing same-source class: "+name)
            if label:
                mass = mix["auxiliary_attack_fraction_within_class"] / len(group_names)
            else:
                mass = min(mix["auxiliary_normal_fraction_max_within_class"]/len(group_names),
                           mix["auxiliary_normal_max_weight_per_connection_within_class"] * len(loc))
            aux[loc] = 0.5 * mass / len(loc)
        remaining = 0.5 - math.fsum(aux[aux_y==label])
        w[ix] = cic_w[ix] * (remaining / math.fsum(cic_w[ix]))
        if not math.isclose(math.fsum(w[ix])+math.fsum(aux[aux_y==label]),0.5,abs_tol=1e-13):
            raise ValueError("class mass")
    if not np.all(w > 0):
        raise ValueError("zero or negative FIT weight")
    return w


class Progress:
    stage = "load"
    def tick(self, done, total):
        pass


def source(project):
    parent = project/"runs/device_context_head_training_v2_20261105"
    sys.path.insert(0,str(parent))
    import worker
    return worker,worker.load(Progress(), False)


def materialize(project, folder, pilot):
    worker, source_data = source(project)
    k = worker.k
    fit = source_data["fit"]
    cal = source_data["cal"]
    fit_y = np.asarray([source_data["rows"][int(i)]["label"] for i in fit], dtype=np.int8)
    if pilot:
        choose = np.concatenate([np.flatnonzero(fit_y==y)[:256] for y in (0,1)])
        fit = fit[choose]
        baseline_w = source_data["w"][choose]
        fit_y = fit_y[choose]
    else:
        baseline_w = source_data["w"]
    cal = np.asarray([i for i in cal if source_data["rows"][int(i)]["label"] == 0],dtype=np.int64)
    if pilot:
        cal = cal[:256]
    for name, ix in [("cic_fit",fit),("cic_cal",cal)]:
        x = np.lib.format.open_memmap(folder/(name+".npy"),mode="w+",dtype=np.float32,shape=(len(ix),790))
        for start in range(0,len(ix),2048):
            pos=ix[start:start+2048]
            x[start:start+len(pos)] = k.normalized(source_data["values"],source_data["q"],pos,source_data["norm"],790).numpy()
        x.flush()
        del x
    normfile=project/"runs/device_context_head_training_v2_20261105/context_normalizer.npz"
    with np.load(folder/"auxiliary.npz",allow_pickle=False) as a, np.load(normfile,allow_pickle=False) as cx:
        xn=((np.log1p(a["context"])-cx["mean"])/cx["scale"]).astype(np.float32)
        features=k.normalized((a["z"],xn),a["q"],np.arange(len(xn)),source_data["norm"],790).numpy()
        np.save(folder/"aux_fit.npy",features,allow_pickle=False)
        aux_y=a["label"].astype(np.int8); groups=a["group"]
        aux_ids=a["uid"]
    mix=json.loads((HERE/"EXPERIMENT.json").read_bytes())["mix"]
    w=training_weights(baseline_w,fit_y,aux_y,groups,mix)
    fit_ids=[source_data["rows"][int(i)]["uid"] for i in fit]
    nr=[source_data["rows"][int(i)] for i in cal]
    cal_ids=[r["uid"] for r in nr]
    if len(set(fit_ids)|set(aux_ids)|set(cal_ids))!=len(fit_ids)+len(aux_ids)+len(cal_ids):
        raise ValueError("source partitions overlap")
    if not pilot and len(fit)!=617908:
        raise ValueError("source training count")
    np.savez(folder/"fit_meta.npz",uid=np.r_[np.asarray(fit_ids),aux_ids],label=np.r_[fit_y,aux_y],
             weights=w,n_cic=len(fit),cic_w=baseline_w,cal_w=k.class_weights(nr),cal_uid=cal_ids)
    if not pilot:
        from compute import write
        aw=w[len(fit):]
        stats=[]
        for g in sorted(set(groups)):
            for label in (0,1):
                mask=(groups==g)&(aux_y==label)
                stats.append(dict(group=str(g),label=label,connections=int(mask.sum()),
                                  weight_within_class=float(2*aw[mask].sum()),
                                  max_connection_weight_within_class=float(2*aw[mask].max())))
        write(folder.parent/"TRAINING_INPUTS.json",dict(cic_fit=len(fit),cic_cal_normal=len(nr),groups=stats,
              ton=json.loads((folder/"TON_SELECTION.json").read_bytes()),
              fit_order_sha256=hashlib.sha256("".join(str(u)+"\n" for u in [*fit_ids,*aux_ids]).encode()).hexdigest(),
              cal_order_sha256=hashlib.sha256("".join(u+"\n" for u in cal_ids).encode()).hexdigest()))


def tensor_batches(model, x):
    with torch.inference_mode():
        return np.concatenate([model(torch.from_numpy(np.array(x[i:i+1024],copy=True))).flatten().numpy()
                               for i in range(0,len(x),1024)])


def train_one(project,folder,seed,pilot):
    sys.path.insert(0,str(project/"runs/device_context_head_training_v2_20261105"))
    import context_core as k
    card=json.loads((HERE/"EXPERIMENT.json").read_bytes())
    hp=json.loads((project/"runs/device_context_head_training_v2_20261105/TRAINING_SPEC_FROZEN.json").read_bytes())["training"]
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model=k.classifier(seed,790)
    torch.manual_seed(seed)
    generator=torch.Generator(device="cpu").manual_seed(seed)
    opt=torch.optim.AdamW(model.parameters(),**hp["optimizer"],amsgrad=False,foreach=False)
    cic=np.load(folder/"cic_fit.npy",mmap_mode="r")
    aux=np.load(folder/"aux_fit.npy",mmap_mode="r")
    with np.load(folder/"fit_meta.npz",allow_pickle=False) as m:
        labels=m["label"].astype(np.float32);w=m["weights"];uids=m["uid"]
        n_cic=int(m["n_cic"]); old_w=m["cic_w"]
    assert len(cic)==n_cic and n_cic+len(aux)==len(w)
    normal=np.flatnonzero(labels[:n_cic]==0)
    tail_weights=old_w[normal]/math.fsum(old_w[normal])
    tail_rows=[dict(uid=str(uids[i]),partition="LEARN",fit_role="FIT",label=0) for i in normal]
    cut=len(normal)
    steps=0
    for epoch in range(1 if pilot else hp["epochs"]):
        with torch.inference_mode():
            raw=np.concatenate([model(torch.from_numpy(cic[normal[i:i+1024]])).flatten().numpy()
                                for i in range(0,cut,1024)])
        tail=k.TailSampler(tail_rows,k.tail_distribution(raw,tail_weights,hp["tail_mass"]),seed,epoch)
        order=torch.randperm(len(labels),generator=generator).numpy()[:n_cic]
        for start in range(0,n_cic,hp["batch_size"]):
            ids=order[start:start+hp["batch_size"]]; mask=ids<n_cic
            x=np.empty((len(ids),790),dtype=np.float32)
            x[mask]=cic[ids[mask]];x[~mask]=aux[ids[~mask]-n_cic]
            opt.zero_grad(set_to_none=True)
            logits=model(torch.from_numpy(x)).flatten()
            neg=model(torch.from_numpy(cic[normal[tail.draw(hp["tail_negative_samples"])]] )).flatten()
            _,_,loss=k.objective_components(logits,torch.from_numpy(labels[ids]),w[ids],len(labels),neg)
            if not torch.isfinite(loss): raise ValueError("nonfinite training objective")
            loss.backward(); opt.step(); steps+=1
        print("seed",seed,"epoch",epoch+1,"updates",steps,flush=True)
        if not pilot:
            from compute import progress
            progress(folder.parent,"train_"+str(seed),f"种子 {seed} 已完成 {steps:,} 次更新",epoch+1,hp["epochs"])
    if not pilot and steps!=card["mix"]["updates_per_head"]:
        raise ValueError("training budget mismatch")
    np.savez(folder/f"head_{seed}.npz",**{k:v.detach().numpy() for k,v in model.state_dict().items()})
    np.save(folder/f"cal_{seed}.npy",tensor_batches(model.eval(),np.load(folder/"cic_cal.npy",mmap_mode="r")))
    return steps
