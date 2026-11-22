"""Verify the named business actions, actual connection lifetimes, and minute counts."""
from collections import defaultdict
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_login_pilot_v1_20261121"))
from audit import NS, inside, join, read, save, write_tables
from schedule import BURST, ORDINARY, RATES, RECOVER


def new_after_close(prior, new, handshakes, packets, *, require_reset=False):
    stream=int(prior["tcp_stream"])
    other=int(new["tcp_stream"])
    if other==stream or prior["client"]!=new["client"]:
        return False
    syn=handshakes[other][0]
    want=4 if require_reset else 5
    return any(p["incoming"] and p["flags"]&want and
               prior["response_frame"]<p["frame"]<syn["frame"] for p in packets[stream])


def scene_callback(plan,stage,counts):
    def check(result,cases,handshakes,packets):
        by_id=defaultdict(list)
        for r in result:
            assert r["normal"] is True
            by_id[r["scenario_id"]].append(r)
        expected={a["scenario_id"]:a for a in plan["actions"] if not a.get("boundary_probe")}
        scheduled_probe={a["scenario_id"]:a for a in plan["actions"] if a.get("boundary_probe")}
        setup={a["scenario_id"]+"-setup":a for a in expected.values() if a["scenario"]==BURST}
        have=set(by_id)&set(scheduled_probe)
        assert (set(by_id)-have)==set(expected)|set(setup)
        assert (1<=len(have)<=len(scheduled_probe)) if stage=="enrollment" else not have
        minute=[]
        verified=defaultdict(int)
        for key,acts in by_id.items():
            first=acts[0]
            label=first["scenario"]
            assert all(r["client"]==first["client"] and r["scenario"]==label for r in acts)
            planned=expected.get(key) or scheduled_probe.get(key) or setup.get(key)
            assert first["client"]==planned["client"]+1
            assert label==(ORDINARY[0] if key in setup else planned["scenario"])
            expected_count={ORDINARY[0]:1,ORDINARY[1]:2,ORDINARY[2]:2,RECOVER:2,
                            BURST:planned.get("scheduled_rate")}[label]
            assert len(acts)==expected_count,("CASE_REQUEST_COUNT",key,len(acts))
            if not all(r["aligned"] for r in acts):
                continue
            outcomes=[r["observed_status"] for r in acts]
            indices=[r["request_index"] for r in acts]
            if label==ORDINARY[0]:
                ok=(outcomes==[200] and indices==[1])
            elif label==ORDINARY[1]:
                ok=outcomes==[401,200] and indices==[1,2] and acts[0]["tcp_stream"]==acts[1]["tcp_stream"]
            elif label==ORDINARY[2]:
                ok=outcomes==[401,200] and indices==[1,1] and new_after_close(*acts,handshakes,packets)
            elif label==RECOVER:
                ok=outcomes==[200,200] and indices==[1,1] and new_after_close(*acts,handshakes,packets,require_reset=True)
            else:
                rate=planned["scheduled_rate"]
                assert rate in RATES
                event,=[e for e in cases[key] if e["event"]=="minute_start"]
                t=event["time_ns"]
                following=[v for v in handshakes.values() if v and t<=v[0]["ns"]<t+60*NS]
                order=sorted(acts,key=lambda a:a["reconnect_step"])
                origin,=by_id[key+"-setup"]
                seq=[origin,*order]
                ok=(event["scheduled_rate"]==rate and outcomes==[200]*rate and indices==[1]*rate and
                    {r["scheduled_rate"] for r in acts}=={rate} and
                    len(following)==rate and
                    {v[0]["frame"] for v in following}=={r["syn_frame"] for r in acts} and
                    all(new_after_close(a,b,handshakes,packets,require_reset=True) for a,b in zip(seq,seq[1:])))
                minute.append(dict(minute=key,client=first["client"],start_ns=t,length_seconds=60,
                                   scheduled=rate,actual=len(following),confirmed=bool(ok),
                                   h60=[a["handshakes_60s"] for a in order]))
            verified[label]+=int(ok)
        groups=[]
        labels=[*ORDINARY,RECOVER if stage=="enrollment" else BURST]
        for label in labels:
            actions=[r for r in result if r["scenario"]==label]
            match=[r for r in actions if r["aligned"]]
            groups.append(dict(scenario=label,cases=len({r["scenario_id"] for r in actions}), proved_cases=verified[label],
                       requests=len(actions), connections=len({r["tcp_stream"] for r in match}),aligned=len(match),
                       unaligned=len(actions)-len(match),observed_200=sum(r["observed_status"]==200 for r in match),
                       observed_401=sum(r["observed_status"]==401 for r in match)))
        counts.extend(sorted(minute,key=lambda m:m["start_ns"]))
        return groups
    return check


def collect_aligned(folder):
    c=read(folder/"CAPTURE.json")
    plan=read(folder/"SCHEDULE.json")
    assert plan["seed"]==c["random_seed"]
    minute=[]
    report,align,fields=join(folder,c,scene_callback(plan,c["scope"],minute))
    write_tables(folder,report,align)
    if c["scope"]=="evaluation":
        assert len(minute)==plan["minute_blocks"] and all(v["confirmed"] for v in minute)
        save(folder/"MINUTES.json",dict(blocks=minute))
    assert report["status"]=="PASS"
    return c,report,align,fields
