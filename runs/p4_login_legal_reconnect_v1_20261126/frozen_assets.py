"""Read and verify the existing normal reference, thresholds and paired controls."""
from contextlib import contextmanager
import csv
from pathlib import Path
import sys
import tarfile
import tempfile

import numpy as np

from protocol_reconnect import ATTACK, HANDSHAKE_CUT, RANK5, REFERENCE, registration

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
ARCHIVE = RUNS/"p4_v14_local_supplements_v1_20261125"
sys.path.insert(0,str(ARCHIVE))
from wsl_replay import combine, dataset, read_batch, reduced, subset
from evidence import verified_archive
from assessment import KEPT, saved_formal
from feature_witness import TON, runtime
from schedule import BURST
from sources import ARMS, HEADS, check_seal, identity, read


@contextmanager
def scoring_runtime(live):
    with tempfile.TemporaryDirectory(prefix="frozen-",dir=live) as name:
        package = Path(name)
        with tarfile.open(TON/".private/package.tar.gz") as archive:
            for entry in archive.getmembers():
                assert entry.isfile() and entry.name==Path(entry.name).name
                (package/entry.name).write_bytes(archive.extractfile(entry).read())
        expected = read(TON/"received/ACCEPTANCE.json")["package_sha256"]
        assert identity(package/"PACKAGE_MANIFEST.json")["sha256"]==expected
        yield runtime(package)


def registry(login):
    formal, rank, attack = (login/name for name in (REFERENCE,RANK5,ATTACK))
    ref, first, final, refs = check_seal(formal)
    rank_files, rank_report = verified_archive(rank)
    attack_files, attack_report = verified_archive(attack)
    release = read(rank/"THRESHOLD_SEAL.json")
    rank_input = read(rank/"INPUTS.json")
    cutfile = rank/"THRESHOLDS.json"
    policy = read(cutfile)
    assert release["status"]==policy["status"]=="PASS" and policy["strict_greater_than"]
    assert release["normal_connections"]==policy["calibration_connections"]==1000
    assert policy["descending_rank"]==5 and tuple(policy["arms"])==ARMS and tuple(policy["heads"])==HEADS
    assert identity(rank/"INPUTS.json")==release["input_manifest"]
    assert identity(cutfile)==release["thresholds"]==rank_report["thresholds"]==attack_report["rank5_thresholds"]
    assert ref["reference"]==rank_report["reference"]==attack_report["reference"]==rank_input["reference"]
    cuts = np.asarray(policy["thresholds"])
    assert cuts.shape==(3,4) and np.isfinite(cuts).all()

    verified = ARCHIVE/"received"
    v14_names = ("WSL_THRESHOLDS.csv","WSL_H60_FOUR_ARMS.csv","WSL_REPLAY.json")
    hashes = dict(x.split("  ",1)[::-1] for x in (verified/"SHA256SUMS").read_text("ascii").splitlines())
    for name in v14_names:
        assert identity(verified/name)["sha256"]==hashes[name]
    assert read(verified/"WSL_REPLAY.json")["status"]=="PASS"
    with (verified/"WSL_THRESHOLDS.csv").open(encoding="utf8",newline="") as stream:
        source = {(row["arm"],row["head"]):row for row in csv.DictReader(stream)}
    for i,arm in enumerate(ARMS):
        for j,head in enumerate(HEADS):
            assert float(source[arm,head]["threshold"])==cuts[i,j]
    count = source["handshake_only","one_rule"]
    assert tuple(int(count[k]) for k in ("threshold","calibration_n","strictly_above","at_threshold"))==(4,1000,0,5)

    rows, saved = saved_formal(formal)
    base = dataset("prior_formal",dict(saved,scores=saved["scores"][KEPT],arms=saved["arms"][KEPT]),rows,True,207)
    stress = subset(base,np.asarray([x["scenario"]==BURST for x in rows]),"historical_51")
    assert len(reduced(stress)[0])==51
    replay = {"low_attack":[], "medium_attack":[]}
    reference_endpoint = [[x["ip"],x["mac"]] for x in first["endpoints"]]
    assert reference_endpoint==rank_input["endpoints"]
    used = set(rank_input["used_instances"])
    latest = max(final["capture"]["end_ns"],release["sealed_at_ns"])
    for entry in rank_report["batches"]:
        archive_receipt = read(rank/entry["path"])
        assert archive_receipt["instance"] not in used
        used.add(archive_receipt["instance"])
        latest = max(latest,archive_receipt["end_ns"])
    last_rank = latest
    for entry in attack_report["batches"]:
        stage = entry["path"].split("/")[0]
        cohort = next((kind for kind in replay if stage.startswith(kind.split("_")[0]+"_")),None)
        if cohort is None:
            continue
        data = read_batch(attack,entry,attack_files,"attack",False)
        assert [[x["ip"],x["mac"]] for x in data["endpoints"]]==reference_endpoint
        assert data["port"]==first["server_port"] and data["start_ns"]>last_rank and data["instance"] not in used
        used.add(data["instance"])
        latest = max(latest,data["end_ns"])
        replay[cohort].append(data)
    assert list(map(len,replay.values()))==[3,3]
    groups = dict(historical_51=stress,**{name:combine(items,name) for name,items in replay.items()})
    assert [len(reduced(item)[0]) for item in groups.values()]==[51,600,600]
    for name,check in {"historical_51":(0,0,5,21),"low_attack":(5,19,549,564),"medium_attack":(35,343,568,564)}.items():
        h, values = reduced(groups[name])
        totals = tuple((values[:,:,3]>cuts[:,3,None]).sum(axis=1)) + (int((h>HANDSHAKE_CUT).sum()),)
        assert totals==check

    primary = ("protocol_reconnect.py","collect_reconnect.py","frozen_assets.py","evaluate_reconnect.py",
               "reconnect_controller.py","results_reconnect.py","METHOD.md")
    code = [*(HERE/name for name in primary),ARCHIVE/"wsl_replay.py"]
    for name, sources in (("p4_login_calibration_v1_20261122",("capture.py","assessment.py")),
                          ("p4_login_formal_v1_20261121",("collect_formal.py","bank.py","frozen_score.py")),
                          ("p4_login_pilot_v1_20261121",("collect.py","audit.py","feature_witness.py"))):
        code.extend(RUNS/name/src for src in sources)
    pin = dict(status="SEALED",plan=registration(),reference_archive=REFERENCE,
               endpoints=reference_endpoint,server_port=first["server_port"],kernel=first["kernel"],
               reference=ref["reference"],reference_rows=4096,components=393,
               reference_manifest=identity(formal/"SHA256SUMS"),reference_files_checked=len(refs),
               rank5_archive=RANK5,rank5_thresholds=identity(cutfile),rank5_archive_files_checked=len(rank_files),
               rank5_manifest=identity(rank/"SHA256SUMS"),calibration_connections=1000,
               rank5_sealed_at_ns=release["sealed_at_ns"],cuts=cuts.tolist(),cic_cuts=rank_input["old_cic_cuts"],
               handshake_threshold=HANDSHAKE_CUT,handshake_threshold_table=identity(verified/"WSL_THRESHOLDS.csv"),
               attack_archive=ATTACK,attack_manifest=identity(attack/"SHA256SUMS"),
               attack_archive_files_checked=len(attack_files),last_prior_capture_ns=latest,
               prior_service_instances=sorted(used),files={p.relative_to(RUNS).as_posix():identity(p) for p in sorted(code)})
    return pin, groups
