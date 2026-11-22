"""Replay the recorded Windows singleton failure from the original reference frames."""
from pathlib import Path
import sys

from frozen_score import e3_batch, sealed_runtime
from audit import identity, join, read, save
from audit_formal import scene_callback
from bank import boundary, packet_stream, select_frozen, snapshots


def replay(source,out):
    defect=read(source/"FAULT_PROBE.json")
    folder=source/"enrollment"
    c=read(folder/"CAPTURE.json")
    pcap=folder/"login.pcap"
    assert identity(pcap)==defect["capture"]
    report,_,fields=join(folder,c,scene_callback(read(folder/"SCHEDULE.json"),"enrollment",[]))
    assert report["status"]=="PASS"
    cut=boundary(c,fields)
    assert cut==defect["window"]
    with sealed_runtime() as (_,pins):
        candidates=[r[0] for r in packet_stream(pcap,c,fields,cut)]
        chosen,components,_=select_frozen(candidates,cut)
        assert len(chosen)==defect["selected"] and components==defect["components"]
        fixed=[]
        for broken in defect["bad_cases"]:
            frame=broken["frame"]
            row,=[r for r in chosen if r["frame"]==frame]
            assert row["uid"]==broken["uid"]
            _,inputs=snapshots(pcap,c,fields,cut,{frame:row["uid"]})
            vector,encoder,batches=e3_batch(inputs,pins)
            assert vector.shape==(1,768) and batches==1
            proof,=encoder["single_thread_singletons"]
            assert proof["uid"]==broken["uid"] and proof["frame"]==frame
            assert proof["original_max_abs_spread"]==broken["base_spread"]
            assert proof["new_max_abs_spread"]==proof["first_row_delta"]==0.
            fixed.append(proof)
    receipt=dict(status="PASS", capture=defect["capture"],source=source.name,selected_rows=len(chosen),
                 reference_candidates=len(candidates),valid_reference_components=components,
                 original_capture_frames=report["checks"]["total_frames"],
                 original_auth_requests=report["checks"]["aligned_requests"],
                 original_connections=report["checks"]["tcp_connections"],boundary=cut,
                 cause=identity(source/"FAULT_PROBE.json"), repaired=fixed,
                 implementation=identity(Path(__file__).resolve().parent.parent/
                                          "p4_login_pilot_v1_20261121/feature_witness.py"))
    save(out/"WINDOWS_REPAIR.json",receipt)
    print(f"WINDOWS_REPAIR PASS {len(fixed)} real singleton batches",flush=True)


if __name__=="__main__":
    replay(*map(Path,sys.argv[1:]))
