"""Measure two single-query paths in separate processes after capture acceptance."""
import os
for flag in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"):
    os.environ[flag] = "4"

from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter_ns

import numpy as np
import psutil

from frozen_assets import HERE, scoring_runtime
from assessment import get_array
from bank import match, packet_stream
from feature_witness import MODEL, NORM, RUNTIME_MANIFEST
from frozen_score import adjusted, calibration, inputs790, models, scores
from audit import tshark_fields
from protocol_reconnect import BENCHMARK_SAMPLES, BENCHMARK_WARMUP, HANDSHAKE_CUT, REFERENCE
from results_reconnect import sha_all
from sources import identity, read, save, table


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


def stats(values,stage,limit,boundary):
    x = np.asarray(values)
    assert x.shape==(BENCHMARK_SAMPLES,) and (x>0).all()
    return dict(path=stage,unit="query",warmup=BENCHMARK_WARMUP,queries=len(x),logical_batch=1,
                encoder_physical_batch=limit,reference_rows=4096,reference_components=393,
                p50_ms=float(np.quantile(x,.5))/1e6,p95_ms=float(np.quantile(x,.95))/1e6,
                per_second=1e9*len(x)/int(x.sum()),peak_rss_bytes=psutil.Process().memory_info().peak_wset,
                latency_ns=x.tolist(),timing_boundary=boundary)


def full(root,out,ref,pin,cfg,pins):
    from constrained_onboarding_reference_v2 import query_descriptor

    source = read(root/"evidence/ACCEPTANCE.json")["batches"][0]
    attempt = (root/"evidence"/source["path"]).parent
    old = get_array(attempt/"SCORES.npz")
    folder = attempt/"holdout"
    cap = read(folder/"CAPTURE.json")
    pcap = folder/"login.pcap"
    fields = tshark_fields(pcap,cap["server_port"])
    stream = packet_stream(pcap,cap,fields,None)
    norm = calibration(pins)
    net = models(root.parent/REFERENCE/"frozen_quick_check_assets")
    encode = physical_encoder(pins)
    cut = np.asarray(pin["cuts"])
    latency, query_list = [], []
    largest = 0.
    for index in range(BENCHMARK_WARMUP+BENCHMARK_SAMPLES):
        frame = int(old["frame"][index])
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
        base = scores(net,inputs790(q["z"],q["q"],q["physical"],norm))
        support,_,_ = match(q,ref,cfg,norm)
        score = np.stack((base,*(adjusted(base,support[i],np.zeros(1,dtype=bool),cfg["method"]) for i in (0,2))))
        flags = score>cut[:,None,:]
        h_flag = h>HANDSHAKE_CUT
        t1 = perf_counter_ns()
        largest = max(largest,float(np.max(np.abs(score[:,0,:]-old["scores"][:,index,:]))))
        assert np.array_equal(flags[:,0,:],old["local_decisions"][:,index,:])
        assert h_flag==old["handshake_only"][index]
        query_list.append(q)
        if index>=BENCHMARK_WARMUP:
            latency.append(t1-t0)
    assert largest<=.0005
    result = stats(latency,"frozen_netFound_full",16,
                   "PCAP record replay after the previous POST through causal updates, snapshot, tokenizer, netFound, 790-D head, matching and four flags. Weights resident. Offline tshark field extraction and process startup outside the latency.")
    result.update(source_batch=source["batch"],pcap=identity(pcap),matched_score_max_abs_error=largest)
    np.savez_compressed(out/"QUERY_FIXTURE.npz",**{k:np.concatenate([q[k] for q in query_list]) for k in query_list[0]})
    save(out/"FULL.json",result)


def match_only(out,ref,cfg,pins):
    fixture = get_array(out/"QUERY_FIXTURE.npz")
    norm = calibration(pins)
    latency = []
    for index in range(BENCHMARK_WARMUP+BENCHMARK_SAMPLES):
        one = {k:v[index:index+1] for k,v in fixture.items()}
        t0 = perf_counter_ns()
        match(one,ref,cfg,norm)
        if index>=BENCHMARK_WARMUP:
            latency.append(perf_counter_ns()-t0)
    result = stats(latency,"matching_only",0,
                   "Existing bank.match with one precomputed query and resident reference arrays. Includes reference normalization, 3D, role diagnostic and multiscale support. Excludes feature encoding, heads and output writes.")
    save(out/"MATCH.json",result)


def main(root,stage=None):
    out = root/"performance"
    pin = read(root/"evidence/REGISTRATION.json")
    assert read(root/"evidence/ACCEPTANCE.json")["status"]=="PASS"
    if stage:
        path = root.parent/REFERENCE/"enrollment/REFERENCE.npz"
        assert identity(path)==pin["reference"]
        ref = get_array(path)
        with scoring_runtime(root/"live") as (cfg,pins):
            if stage=="full":
                full(root,out,ref,pin,cfg,pins)
            else:
                assert stage=="match"
                match_only(out,ref,cfg,pins)
        return
    out.mkdir(exist_ok=False)
    for key in ("full","match"):
        subprocess.run([sys.executable,"-B","-X","utf8",str(__file__),str(root),key],check=True,timeout=380)
    meta = subprocess.run(["powershell.exe","-NoProfile","-Command",
            "$c=Get-CimInstance Win32_Processor | Select-Object -First 1; "
            "[pscustomobject]@{cpu=$c.Name;cores=$c.NumberOfCores;logical=$c.NumberOfLogicalProcessors;"
            "ram=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory} | ConvertTo-Json -Compress"],
            check=True,capture_output=True,encoding="utf8",timeout=10)
    import json
    hardware = json.loads(meta.stdout)
    results = [read(out/name) for name in ("MATCH.json","FULL.json")]
    columns = ("path","unit","warmup","queries","logical_batch","encoder_physical_batch","reference_rows",
               "reference_components","p50_ms","p95_ms","per_second","peak_rss_bytes","timing_boundary")
    table(out/"PERFORMANCE.csv",[dict(**{k:r[k] for k in columns},cpu=hardware["cpu"],cores=hardware["cores"],
          logical_cores=hardware["logical"],ram_bytes=hardware["ram"],os=platform.platform(),device="CPU",
          numerical_threads=4,peak_definition="Windows process lifetime peak working set, separate worker per path")
          for r in results])
    receipt = dict(status="PASS",hardware=hardware,source=identity(root/"evidence/ACCEPTANCE.json"),
                   result=identity(out/"PERFORMANCE.csv"),timing="sequential single query, throughput = n / sum latency")
    save(out/"ACCEPTANCE.json",receipt)
    files = sha_all(out)
    save(root/"live/BENCHMARK_STATUS.json",dict(**receipt,files=files,table=str(out/"PERFORMANCE.csv")))
    print("Local single-query benchmark PASS",flush=True)


if __name__=="__main__":
    main(Path(sys.argv[1]),*sys.argv[2:])
