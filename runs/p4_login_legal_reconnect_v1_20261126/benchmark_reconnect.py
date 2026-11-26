"""Measure the frozen single-query scoring and matching paths in separate processes."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from time import perf_counter_ns

for flag in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[flag] = "4"

import numpy as np
import psutil
from threadpoolctl import threadpool_info

from frozen_assets import scoring_runtime
from assessment import get_array
from bank import match, packet_stream
from feature_witness import MODEL, NORM, RUNTIME_MANIFEST
from frozen_score import adjusted, calibration, digest_order, inputs790, models, scores
from audit import HISTORY, tshark_fields
from protocol_reconnect import BENCHMARK_SAMPLES, BENCHMARK_WARMUP, HANDSHAKE_CUT, REFERENCE
from results_reconnect import sha_all
from sources import ARMS, HEADS, identity, read, save, table

REPLAY_COUNT = BENCHMARK_WARMUP + BENCHMARK_SAMPLES


def bind_inputs(root):
    evidence = root/"evidence"
    manifest = evidence/"SHA256SUMS"
    state = read(root/"live/RUN_STATUS.json")
    assert state["stage"]=="ACCEPTED" and state["manifest"]==identity(manifest)
    hashes = {name: sha for sha,name in (line.split("  ",1) for line in manifest.read_text("ascii").splitlines())}

    def sealed(name):
        path = (evidence/name).resolve()
        assert path.is_relative_to(evidence.resolve()) and identity(path)["sha256"]==hashes[name]
        return path

    accepted = read(sealed("ACCEPTANCE.json"))
    assert accepted["status"]=="PASS" and accepted["qualified_posts"]==600
    source = accepted["batches"][0]
    attempt = sealed(source["path"]).parent
    receipt = read(attempt/"BATCH_ACCEPTANCE.json")
    assert identity(attempt/"BATCH_ACCEPTANCE.json")==source["receipt"]
    assert receipt["status"]=="PASS" and receipt["eligible_posts"]>=REPLAY_COUNT
    names = ("SCORES.npz","QUALIFIED_ROSTER.json","holdout/login.pcap","holdout/CAPTURE.json",
             "holdout/PACKET_ACCEPTANCE.json")
    for name in names:
        path = sealed((attempt/name).relative_to(evidence).as_posix())
        assert identity(path)==receipt["files"][name]
    pins = read(sealed("REGISTRATION.json"))
    reference = root.parent/REFERENCE/"enrollment/REFERENCE.npz"
    threshold = root.parent/pins["rank5_archive"]/"THRESHOLDS.json"
    assert identity(reference)==pins["reference"]==accepted["reference"]
    assert identity(threshold)==pins["rank5_thresholds"]==accepted["thresholds"]
    capture = read(attempt/"holdout/PACKET_ACCEPTANCE.json")
    history = capture["checks"]["verified_history_source"]
    history_package = read(HISTORY/"PACKAGE_MANIFEST.json")["files"]
    for name in ("history_common.py","history_stream.py"):
        assert identity(HISTORY/name)==history[name] and history[name]["sha256"]==history_package[name]
    return pins, attempt, dict(
        capture_batch=source["batch"], batch_acceptance=source["receipt"], accepted_capture=identity(sealed("ACCEPTANCE.json")),
        accepted_manifest=identity(manifest), registration=identity(sealed("REGISTRATION.json")),
        data_files={name:receipt["files"][name] for name in names}, reference=pins["reference"],
        thresholds=pins["rank5_thresholds"], history_source=history, history_package=identity(HISTORY/"PACKAGE_MANIFEST.json"),
        sample=f"first {REPLAY_COUNT} eligible POSTs in the registered first capture, sorted in original frame order",
        warmup=BENCHMARK_WARMUP, timed_queries=BENCHMARK_SAMPLES)


def accepted_scores(attempt, pin):
    old = get_array(attempt/"SCORES.npz")
    qualified = read(attempt/"QUALIFIED_ROSTER.json")
    assert digest_order(old["uid"])==qualified["ordered_uid_sha256"]
    assert old["uid"].tolist()==qualified["uid"] and old["stream"].tolist()==qualified["connections"]
    assert (np.diff(old["frame"])>0).all() and len(set(old["uid"]))==len(old["uid"])
    assert tuple(old["arms"])==ARMS and tuple(old["head_names"])==HEADS
    assert np.array_equal(old["local_cuts"],pin["cuts"])
    assert np.array_equal(old["local_decisions"],old["scores"]>old["local_cuts"][:,None,:])
    assert np.array_equal(old["handshake_only"],old["h"]>HANDSHAKE_CUT)
    return old


def load_history():
    sys.path.insert(0,str(HISTORY))
    import history_common
    import history_stream
    assert Path(history_common.__file__).resolve()==(HISTORY/"history_common.py").resolve()
    assert Path(history_stream.__file__).resolve()==(HISTORY/"history_stream.py").resolve()


def physical_encoder(pins):
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from hnr.encoding import new_encoder, physical_batch
    from ton_recent import verify_tokenized

    config = dict(runtime_root=str(MODEL),normalizer=str(NORM),normalizer_sha256=pins["e3_normalizer"]["sha256"],
                  runtime_files_manifest=dict(path=str(RUNTIME_MANIFEST),sha256=pins["history_runtime_manifest"]["sha256"]))
    generator,_ = new_encoder(config)
    embed,_,net,tokenizer,collator = generator

    def encode(flow,witness):
        token = tokenize(tokenizer,flow)
        verify_tokenized(flow,witness,token)
        batch = collator([token])
        verify_batch([token],batch)
        physical,count = physical_batch(batch,1,tensor_hash)
        z = embed.core.e3_forward_batches(net,[physical],"cpu")
        assert count==16 and z.shape==(16,768) and z.dtype==np.float32 and np.isfinite(z).all()
        assert float(np.max(np.abs(z-z[:1])))<=64*np.finfo(np.float32).eps
        return z[:1]
    return encode


def stats(values,stage,physical,start,stop,preprocess):
    x = np.asarray(values)
    assert x.shape==(BENCHMARK_SAMPLES,) and (x>0).all()
    torch = sys.modules.get("torch")
    rss = psutil.Process().memory_info().peak_wset
    return dict(path=stage,unit="query",pid=os.getpid(),warmup=BENCHMARK_WARMUP,queries=len(x),logical_batch=1,
                encoder_physical_batch=physical,reference_rows=4096,reference_components=393,
                p50_ms=float(np.quantile(x,.5))/1e6,p95_ms=float(np.quantile(x,.95))/1e6,
                per_second=1e9*len(x)/int(x.sum()),peak_rss_bytes=rss,peak_rss_mib=rss/2**20,
                latency_ns=x.tolist(),timed_total_ms=int(x.sum())/1e6,timing_start=start,timing_stop=stop,
                pcap_preprocessing=preprocess,threadpool_info=threadpool_info(),
                torch_intraop_threads=torch.get_num_threads() if torch else None,
                torch_interop_threads=torch.get_num_interop_threads() if torch else None)


def correct(raw,support,method):
    flags = np.zeros(len(raw),dtype=bool)  # Eligible incoming login POSTs.
    return np.stack((raw,*(adjusted(raw,support[i],flags,method) for i in (0,2))))


def full(root,out,attempt,old,ref,cfg,pins):
    from constrained_onboarding_reference_v2 import query_descriptor

    load_history()
    folder = attempt/"holdout"
    cap = read(folder/"CAPTURE.json")
    pcap = folder/"login.pcap"
    fields = tshark_fields(pcap,cap["server_port"])
    stream = packet_stream(pcap,cap,fields,None)
    norm = calibration(pins)
    net = models(root.parent/REFERENCE/"frozen_quick_check_assets")
    encode = physical_encoder(pins)
    cut = old["local_cuts"]
    latency, queries, supports, observed = [], [], [], []
    for index,frame in enumerate(old["frame"][:REPLAY_COUNT]):
        t0 = perf_counter_ns()
        while True:
            row,context,x,h,role,port,_,inbound = next(stream)
            if row["frame"]>=frame:
                break
        assert row["frame"]==frame and row["uid"]==old["uid"][index] and inbound and h==old["h"][index]
        flow,numeric,witness = context.snapshot()
        desc,_ = query_descriptor(dict(flow=flow,state=numeric,provenance=witness,
                                      source_sha256=row["source_sha256"]),row)
        q = dict(z=encode(flow,witness),q=np.asarray(desc,dtype=np.float32)[None,:],
                 physical=np.asarray(x,dtype=np.float64)[None,:],role=np.asarray([role]),
                 port=np.asarray([port]),h=np.asarray([h]))
        raw = scores(net,inputs790(q["z"],q["q"],q["physical"],norm))
        support,_,_ = match(q,ref,cfg,norm)
        values = correct(raw,support,cfg["method"])
        alarms = values>cut[:,None,:]
        handshake_alarm = h>HANDSHAKE_CUT
        t1 = perf_counter_ns()
        assert np.array_equal(alarms[:,0,:],old["local_decisions"][:,index,:])
        assert handshake_alarm==old["handshake_only"][index]
        queries.append(q)
        supports.append(support)
        observed.append(values)
        if index>=BENCHMARK_WARMUP:
            latency.append(t1-t0)
    largest = float(np.max(np.abs(np.concatenate(observed,axis=1)-old["scores"][:,:REPLAY_COUNT,:])))
    assert largest<=.0005
    fixture = {k:np.concatenate([q[k] for q in queries]) for k in queries[0]}
    np.savez_compressed(out/"QUERY_FIXTURE.npz",**fixture,uid=old["uid"][:REPLAY_COUNT],
                        frame=old["frame"][:REPLAY_COUNT],full_support=np.concatenate(supports,axis=1))
    result = stats(latency,"frozen_netFound_full",16,
                   "After previous selected POST, before advancing the PCAP record iterator to the current POST",
                   "Four decisions ready after causal state, netFound, 790-D heads, reference matching and thresholds",
                   "tshark field extraction, TCP stream and HTTP POST parsing, UID selection and model load outside timer. Sequential record reads and causal state updates inside timer.")
    result.update(verified_queries=REPLAY_COUNT, matched_score_max_abs_error=largest,
                  verdict_mismatches=0, uid_order=digest_order(old["uid"][:REPLAY_COUNT]))
    save(out/"FULL.json",result)


def match_only(out,old,ref,cfg,pins):
    fixture = get_array(out/"QUERY_FIXTURE.npz")
    assert np.array_equal(fixture.pop("uid"),old["uid"][:REPLAY_COUNT])
    assert np.array_equal(fixture.pop("frame"),old["frame"][:REPLAY_COUNT])
    expected = fixture.pop("full_support")
    norm = calibration(pins)
    latency, supports = [], []
    for index in range(REPLAY_COUNT):
        one = {k:v[index:index+1] for k,v in fixture.items()}
        t0 = perf_counter_ns()
        support,_,_ = match(one,ref,cfg,norm)
        t1 = perf_counter_ns()
        supports.append(support)
        if index>=BENCHMARK_WARMUP:
            latency.append(t1-t0)
    actual = np.concatenate(supports,axis=1)
    support_delta = float(np.max(np.abs(actual-expected)))
    values = correct(old["scores"][0,:REPLAY_COUNT,:],actual,cfg["method"])
    alarms = values>old["local_cuts"][:,None,:]
    assert np.array_equal(alarms,old["local_decisions"][:,:REPLAY_COUNT,:])
    assert np.array_equal(fixture["h"]>HANDSHAKE_CUT,old["handshake_only"][:REPLAY_COUNT])
    result = stats(latency,"matching_only",0,
                   "Precomputed single query and reference arrays resident, immediately before existing bank.match",
                   "Matching returns 3D, R2 diagnostic and multiscale support and component counts",
                   "No PCAP read, parsing or encoder in this worker's timed path. Reference normalization is part of bank.match.")
    result.update(verified_queries=REPLAY_COUNT, support_max_abs_diff_from_full=support_delta,verdict_mismatches=0,
                  uid_order=digest_order(old["uid"][:REPLAY_COUNT]))
    save(out/"MATCH.json",result)


def report(root,out):
    meta = subprocess.run(["powershell.exe","-NoProfile","-Command",
            "$c=Get-CimInstance Win32_Processor | Select-Object -First 1; "
            "[pscustomobject]@{cpu=$c.Name;cores=$c.NumberOfCores;logical=$c.NumberOfLogicalProcessors;"
            "ram=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory} | ConvertTo-Json -Compress"],
            check=True,capture_output=True,encoding="utf8",timeout=10)
    hardware = json.loads(meta.stdout)
    results = [read(out/name) for name in ("MATCH.json","FULL.json")]
    match_result, full_result = results
    assert match_result["pid"]!=full_result["pid"] and match_result["uid_order"]==full_result["uid_order"]
    for result in results:
        assert result["verified_queries"]==REPLAY_COUNT and result["verdict_mismatches"]==0
    columns = ("path","unit","pid","warmup","queries","logical_batch","encoder_physical_batch","reference_rows",
               "reference_components","p50_ms","p95_ms","per_second","peak_rss_mib","timed_total_ms",
               "timing_start","timing_stop","pcap_preprocessing","torch_intraop_threads","torch_interop_threads")
    table(out/"PERFORMANCE.csv",[dict(**{k:r[k] for k in columns},cpu=hardware["cpu"],cores=hardware["cores"],
          logical_cores=hardware["logical"],ram_gib=hardware["ram"]/2**30,os=platform.platform(),device="CPU",
          library_threads="; ".join(f"{p['prefix']}={p['num_threads']}" for p in r["threadpool_info"]),
          requested_numerical_threads=4,peak_definition="Windows peak working set since child process startup")
          for r in results])
    receipt = dict(status="PASS",hardware=hardware,source=identity(root/"evidence/ACCEPTANCE.json"),
                   pinned_inputs=identity(out/"PINNED_INPUTS.json"),benchmark_source=identity(Path(__file__)),
                   result=identity(out/"PERFORMANCE.csv"),timing="sequential queries per second = timed query count / sum of measured durations",
                   quantiles="linear interpolation",verdict_check=dict(queries_per_worker=REPLAY_COUNT,timed_queries=BENCHMARK_SAMPLES,
                      three_seed_heads_and_ensemble=True,all_four_arms=True,decision_mismatches=0,
                      full_max_abs_score_diff=full_result["matched_score_max_abs_error"],
                      match_support_max_abs_diff=match_result["support_max_abs_diff_from_full"]),
                   raw_stage_records={name:identity(out/name) for name in ("MATCH.json","FULL.json")})
    save(out/"ACCEPTANCE.json",receipt)
    count = sha_all(out)
    save(root/"live/BENCHMARK_STATUS.json",dict(**receipt,files=count,table=str(out/"PERFORMANCE.csv"),
                                              hash_manifest=identity(out/"SHA256SUMS")))
    print("Local single-query benchmark PASS",flush=True)


def main(root,out,stage=None):
    pin,attempt,provenance = bind_inputs(root)
    if stage:
        assert read(out/"PINNED_INPUTS.json")==provenance
        old = accepted_scores(attempt,pin)
        ref = get_array(root.parent/REFERENCE/"enrollment/REFERENCE.npz")
        assert len(ref["uid"])==4096 and len(set(ref["component"]))==393
        with scoring_runtime(root/"live") as (cfg,pins):
            if stage=="full":
                full(root,out,attempt,old,ref,cfg,pins)
            else:
                match_only(out,old,ref,cfg,pins)
        return
    out.mkdir(exist_ok=False)
    old_status = root/"live/BENCHMARK_STATUS.json"
    if old_status.is_file() and read(old_status)["status"]=="FAILED":
        shutil.copyfile(old_status,out/"PRIOR_FAILURE.json")
    save(out/"PINNED_INPUTS.json",provenance)
    for key in ("full","match"):
        print("Benchmarking",key,flush=True)
        subprocess.run([sys.executable,"-B","-X","utf8",str(__file__),str(root),
                        "--output",str(out),"--stage",key],check=True,timeout=380)
    report(root,out)


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--stage",choices=("full","match"))
    args = parser.parse_args()
    main(args.root,args.output or args.root/"performance",args.stage)
