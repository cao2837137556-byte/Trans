"""Independent local summary audit; never changes frozen scores or remote arrays."""
import hashlib,json,math
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];checks=0
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def check(v,msg):
 global checks
 checks+=1
 if not v:raise AssertionError(msg)
def near(a,b,msg):check(abs(a-b)<2e-10,msg)
d=read(P/"DIAGNOSE_RESULT.json");pre=read(P/"PREFLIGHT_RESULT.json")
receipt=read(P/"EVALUATION_COMPLETION.json")
for n,h in receipt["receipt_sha256"].items():check(hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n)
for n,h in read(P/"DELIVERY.json")["pins"].items():check(hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n)
for phase in ["PREFLIGHT","DIAGNOSE"]:
 check("|COMPLETED|0:0|" in read(P/(phase+"_SCHEDULER.json"))["stdout"],phase)
for x in [d,pre]:check(x["status"]=="PASS" and not x["training"] and not x["deployment_change"],"scope")
old_edge=read(ROOT/"runs/device_context_evaluation_v1_20261105/EDGE_RESULT.json")
old_ab=read(ROOT/"runs/device_context_evaluation_v1_20261105/AB_RESULT.json")
for pool,o in d["pools"].items():
 for method,heads in o["metrics"].items():
  for head,roles in heads.items():
   for role,v in roles.items():
    n=v["rows"];a=v["alarm_count"];check(0<=a<=n,"count");near(v["sample_rate"],a/n,"rate");check(0<=v["hierarchical_rate"]<=1+1e-12,"weights")
    raw=o["metrics"]["RAW"][head][role];check(v["added_vs_RAW"]==0 and raw["alarm_count"]-a==v["removed_vs_RAW"],"ceiling")
    if method in ["RAW","C5_FROZEN"]:
     oldmethod="RAW" if method=="RAW" else "C5_P3"
     if pool=="EDGE":
      t=old_edge["arms"]["FUSION790"]["methods"][oldmethod]["heads"][head]["roles"][role]
      check((a,n)==(t["alarm_count"],t["selected_rows"]),"old counts")
      near(v["hierarchical_rate"],t["selected_hierarchical_alarm_rate"],"old weighted")
      near(v["HT_rate"],t["ht_population_alarm_estimate"],"old HT")
     else:
      t=old_ab["pools"][pool]["primary"]["FUSION790"][oldmethod][head]["groups"]["pool"][role.lower()]
      check((a,n)==(t["alarm_count"],t["rows"]),"old AB counts");near(v["hierarchical_rate"],t["weighted_rate"],"old AB weighted")
    if method.startswith("C5_3D"):
     t=o["metrics"][method.replace("3D","2D")][head][role]
     for key in ["alarm_count","sample_rate","hierarchical_rate"]:check(v[key]+1e-10>=t[key],"same bank geometry monotonicity")
 for arm,q in o["signed_contributions"].items():
  check(q["score_max_error"]<.002,"model forward")
  for head,groups in q["groups"].items():
   for group,v in groups.items():
    if not v["rows"]:continue
    for f,t in v["fields"].items():
     for key in ["negative_ig_fraction","gradient_negative_fraction"]:check(0<=t[key]<=1,"signed fraction")
 for key in ["large_artifacts","physical_artifact"]:
  if key in o:
   check(len(o[key]["sha256"])==64 and o[key]["bytes"]>0,"remote manifest")
e=d["pools"]["EDGE"]
for role,v in e["task1_raw_misses"].items():
 g=v["groups"];check(v["rows"]==e["metrics"]["RAW"]["ensemble"][role]["rows"]-e["metrics"]["RAW"]["ensemble"][role]["alarm_count"],"miss totals")
 check(sum(g[k]["rows"] for k in ["warm_or_noninbound","mature_inbound_high_pps","mature_inbound_normal_range_pps"])==v["rows"],"exclusive partition")
 check(g["warm_lt1"]["rows"]<=g["warm_lt10"]["rows"]<=g["warm_or_noninbound"]["rows"],"warm nesting")
 for k,t in g.items():near(t["fraction"],t["rows"]/v["rows"],"fraction")
for head,v in e["task2_false_alarms"].items():
 check(sum(t["rows"] for t in v["categories"].values())==v["rows"]==e["metrics"]["C5_FROZEN"][head]["NORMAL"]["alarm_count"],"FP partition")
 for cat,t in v["categories"].items():
  near(t["fraction"],t["rows"]/v["rows"],"FP fraction");check(sum(t["reasons"].values())==t["rows"],"reason counts");check(0<=t["above_max_cap"]<=t["above_support_scaled_cap"]<=t["rows"],"cap bounds")
w=e["task2_http_withdrawals"];methods=old_edge["arms"]["FUSION790"]["methods"]
x=methods["RAW"]["heads"]["ensemble"]["roles"]["HTTP"]["strata"];y=methods["C5_P3"]["heads"]["ensemble"]["roles"]["HTTP"]["strata"]
expected={k:t["alarm_count"]-y[k]["alarm_count"] for k,t in x.items() if t["alarm_count"]!=y[k]["alarm_count"]}
check(w["strata"]==expected,"withdraw original strata");check(sum(expected.values())==w["rows"]==967,"withdraw total")
check(expected!={"PSH_ACK":842,"ACK_ONLY":123,"SYN_NO_ACK":2},"old wrong expectation regression")
check(w["both_old_matches_outside_context_radius"]<=w["rows"],"context count")
for suffix,method in [("current","C5_3D_FUSION"),("old","C5_3D_OLD")]:
 remaining=w["rows"]-w["recovered_3d_"+suffix];total=e["metrics"][method]["ensemble"]["HTTP"]["removed_vs_RAW"]
 check(0<=remaining<=total,"new withdrawals accounted")
check(d["calibration"]==pre["calibration"],"frozen calibration")
for proto in ["6","17"]:check(d["calibration"]["protocols"][proto]["rho_c"]>0,"positive radius")
summary=dict(status="PASS",checks=checks,scope="LOCAL_SUMMARY_SHA_AND_FROZEN_BASELINE_AUDIT",engineering="PASS",scientific_target="NO_GO",training=False,deployment_change=False,withdrawal_strata=expected,post_result_repair="Expected strata derived from frozen source, remote artifacts unchanged",remote_arrays_reloaded=False,result_sha256=hashlib.sha256((P/"DIAGNOSE_RESULT.json").read_bytes()).hexdigest())
(P/"FINAL_ACCEPTANCE.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps(summary,ensure_ascii=False))
