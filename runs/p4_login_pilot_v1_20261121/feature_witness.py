"""Generate frozen v12 feature witnesses from real, causally aligned POST frames."""
import argparse
from collections import defaultdict
import hashlib
import ipaddress
import os
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import time

from audit import PROJECT, identity, join, read, save, timestamp

TON = PROJECT/"runs/p4_ton_password_frozen_v12_20261118"
FROZEN = PROJECT/"runs/unified_reference_bank_k8192_v1_20261113/.private/early_183987_mo0f7h3d"
DEP = PROJECT/"runs/diagnostics_step2_r2_v1_20261025/benchmark_deps"
MODEL = PROJECT/"runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime"
RUNTIME_MANIFEST = PROJECT/"runs/history_normal_reference_keyrepair_v1_20261031/config/ENCODER_RUNTIME_FILES.json"
NORM = PROJECT/"runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/normalizer.npz"
CTX_NORM = PROJECT/"runs/device_context_head_training_v2_20261105/context_normalizer.npz"


def runtime(package):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sys.path[:0] = list(map(str,(package,FROZEN,FROZEN/"repo/ood",DEP)))
    from frozen_env import setup
    _, _, cfg, _ = setup(PROJECT, local_runtime=FROZEN)
    pins = read(FROZEN/"REMOTE_ASSET_PINS.json")["files"]
    assert identity(RUNTIME_MANIFEST)["sha256"] == pins["history_runtime_manifest"]["sha256"]
    assert identity(NORM)["sha256"] == pins["e3_normalizer"]["sha256"]
    return cfg, pins


def frame_inputs(fields, topology, pcap_hash, anchors):
    from constrained_onboarding_reference_v2 import query_descriptor
    from frontend import meta, new_context
    from vendor.stream_core import Engine

    host = topology["endpoints"][0]
    owner = host["mac"]
    scope = "login_pilot"
    ctx = new_context(scope, {owner}, numeric=True)
    device = Engine()
    config = dict(sources={scope:dict(sha256=pcap_hash)})
    found = []
    for row in fields:
        frame = int(row["frame.number"])
        epoch = timestamp(row)
        if not row["tcp.stream"]:
            assert ctx.frame+1 == frame
            ctx.frame, ctx.previous_ns = frame, epoch
            device.advance(frame,epoch,scope)
            continue
        row["ton.owner.src"] = row["eth.src"] if row["eth.src"] == owner else ""
        row["ton.owner.dst"] = row["eth.dst"] if row["eth.dst"] == owner else ""
        incoming = bool(row["ton.owner.dst"])
        update = None
        if incoming:
            src = int(ipaddress.IPv4Address(row["ip.src"]))
            dst = int(ipaddress.IPv4Address(row["ip.dst"]))
            ports = int(row["tcp.srcport"]),int(row["tcp.dstport"])
            update = (owner,6,int(row["ip.len"]),src,struct.pack("!BIIHH",6,src,dst,*ports))
        device.advance(frame,epoch,scope,update)
        bound_owner, namespace, _ = ctx.append(row)
        if frame not in anchors:
            continue
        assert incoming and bound_owner == owner
        ctx.require_target()
        flow, state, provenance = ctx.states[namespace].snapshot()
        body = dict(flow=flow, state=state, provenance=provenance, source_sha256=pcap_hash)
        metadata = meta(config,scope,frame,epoch,owner,host["ip"],6,namespace[-1],"normal")
        assert metadata["uid"] == anchors[frame]["capture_uid"]
        q, _ = query_descriptor(body,metadata)
        found.append((metadata["uid"],frame,flow,provenance,q,device.features(owner,6)))
    assert len(found) == len(anchors)
    return found


def e3_batch(inputs, pins):
    import numpy as np
    import torch
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from hnr.encoding import new_encoder, physical_batch
    from ton_recent import verify_tokenized

    config = dict(runtime_root=str(MODEL), normalizer=str(NORM), normalizer_sha256=pins["e3_normalizer"]["sha256"],
                  runtime_files_manifest=dict(path=str(RUNTIME_MANIFEST),sha256=pins["history_runtime_manifest"]["sha256"]))
    generator, runtime_id = new_encoder(config)
    embed, _, net, tokenizer, collator = generator
    grouped = defaultdict(list)
    for idx, (_, _, flow, prov, _, _) in enumerate(inputs):
        sample = tokenize(tokenizer,flow)
        verify_tokenized(flow,prov,sample)
        shape = len(sample["dataset_burst_sizes"]), max(sample["dataset_burst_sizes"])+1
        grouped[shape].append((idx,sample))
    features = np.empty((len(inputs),768),dtype=np.float32)
    batches = 0
    singleton_repairs = []
    for values in grouped.values():
        for offset in range(0,len(values),16):
            use = values[offset:offset+16]
            examples = [v for _,v in use]
            logical = len(examples)
            batch = collator(examples)
            verify_batch(examples,batch)
            physical, count = physical_batch(batch,logical,tensor_hash)
            result = embed.core.e3_forward_batches(net,[physical],"cpu")
            assert result.shape == (count,768) and result.dtype == np.float32 and np.isfinite(result).all()
            if count > logical:
                if not np.array_equal(result,np.broadcast_to(result[0],result.shape)) and sys.platform=="win32":
                    uid,frame=inputs[use[0][0]][:2]
                    previous=result
                    threads=torch.get_num_threads()
                    try:
                        torch.set_num_threads(1)
                        result=embed.core.e3_forward_batches(net,[physical],"cpu")
                    finally:
                        torch.set_num_threads(threads)
                    assert result.shape==previous.shape and result.dtype==previous.dtype and np.isfinite(result).all()
                    singleton_repairs.append(dict(uid=uid,frame=frame,threads_before=threads,
                        original_max_abs_spread=float(np.max(np.abs(previous-previous[0]))),
                        new_max_abs_spread=float(np.max(np.abs(result-result[0]))),
                        first_row_delta=float(np.max(np.abs(result[0]-previous[0])))))
                assert np.array_equal(result,np.broadcast_to(result[0],result.shape))
            features[[i for i,_ in use]] = result[:logical]
            batches += 1
    if singleton_repairs:
        runtime_id=dict(**runtime_id,single_thread_singletons=singleton_repairs)
    return features, runtime_id, batches


def _witness(package, out, report, align, fields, requested_norm, limit):
    start = time.monotonic()
    _, pins = runtime(package)
    import numpy as np
    import torch

    anchors = {x["frame"]:x for x in align if x["aligned"]}
    if limit:
        anchors = dict(sorted(anchors.items())[:limit])
    assert len(anchors)
    topology = read(out/"CAPTURE.json")
    inputs = frame_inputs(fields,topology,report["pcap"]["sha256"],anchors)
    z, rt, batches = e3_batch(inputs,pins)
    q = np.stack([t[-2] for t in inputs]).astype(np.float32)
    x = np.asarray([t[-1] for t in inputs],dtype=np.float64)
    raw = np.column_stack((z, q, x)).astype("<f4")
    assert q.shape == (len(z),14) and x.shape == (len(z),8) and raw.shape == (len(z),790)
    assert np.isfinite(raw).all() and np.all((q >= 0) & (q <= 1)) and np.all(x >= 0)
    ctx_norm = requested_norm or CTX_NORM
    source = pins["context_normalizer"]["sha256"]
    final_sha = None
    if ctx_norm.is_file():
        assert identity(ctx_norm)["sha256"] == source
        with np.load(NORM,allow_pickle=False) as a, np.load(ctx_norm,allow_pickle=False) as c:
            assert a["mean"].shape == a["scale"].shape == (768,) and c["mean"].shape==c["scale"].shape==(8,)
            assert np.all(a["scale"] > 0) and np.all(c["scale"] > 0)
            # Identical element formulas to query_tail_core_v2 and reference_assets.forward.
            ze = ((z.astype(np.float64)-a["mean"])/a["scale"]).astype(np.float32)
            xc = ((np.log1p(x)-c["mean"])/c["scale"]).astype(np.float32)
            normal = np.column_stack((ze,q,xc)).astype("<f4")
        assert normal.shape == raw.shape and np.isfinite(normal).all()
        final_sha = hashlib.sha256(normal.tobytes()).hexdigest()
    return dict(status="PASS" if final_sha else "SOURCE_CONTEXT_NORMALIZER_MISSING", real_frames=len(inputs),
                columns=dict(frozen_netfound=768,query_attributes=14,device_stats=8), shape=list(raw.shape),
                raw_components_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),
                frozen_790_input_sha256=final_sha, context_normalizer_expected_sha256=source,
                e3_normalizer_sha256=pins["e3_normalizer"]["sha256"], encoder=rt,
                request_uid_order_sha256=hashlib.sha256("".join(t[0]+"\n" for t in inputs).encode("ascii")).hexdigest(),
                capture_sha256=report["pcap"]["sha256"], physical_forward_batches=batches,
                numpy=np.__version__, torch=torch.__version__, elapsed_seconds=time.monotonic()-start)


def witness(out, report, align, fields, requested_norm=None, limit=None):
    staging = Path(__file__).resolve().parent/".private"
    staging.mkdir(exist_ok=True)
    accepted = read(TON/"received/ACCEPTANCE.json")["package_sha256"]
    with tempfile.TemporaryDirectory(dir=staging) as temp:
        package = Path(temp)
        with tarfile.open(TON/".private/package.tar.gz") as archive:
            for entry in archive.getmembers():
                assert entry.isfile() and entry.name == Path(entry.name).name
                (package/entry.name).write_bytes(archive.extractfile(entry).read())
        assert identity(package/"PACKAGE_MANIFEST.json")["sha256"] == accepted
        return _witness(package,out,report,align,fields,requested_norm,limit)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("capture",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--context-normalizer",type=Path)
    p.add_argument("--limit",type=int)
    a = p.parse_args()
    parsed = read(a.capture/"CAPTURE.json")
    packet, align, fields = join(a.capture,parsed)
    result = witness(a.capture,packet,align,fields,a.context_normalizer,a.limit)
    save(a.output,result)
    print(result["status"],result["shape"],result["elapsed_seconds"])
