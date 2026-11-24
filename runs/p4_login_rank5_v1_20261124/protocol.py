"""Pre-register fixed cohort sizes and preserve the established daily mix."""
from collections import Counter
import heapq
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parent
CAL=ROOT.parent/"p4_login_calibration_v1_20261122"
sys.path.insert(0,str(CAL))
from sources import SOURCE_ID
from plans import SCENARIOS,WEIGHTS
from schedule import ORDINARY,RECOVER

PRIOR="calibration_20261122_ad0fc3"
FIXED="normal_extension_20261122_22c2c0"
OLD_CONNECTIONS=206
CAL_CONNECTIONS=1000
RANK=5


def per_case(scenario):
    return 2 if scenario in (ORDINARY[2],RECOVER) else 1


def plan(stage,index,seed,n):
    rng=random.Random(seed)
    actions=[]
    if stage=="preflight":
        actions=[dict(client=i%3,offset_s=.25+2.3*i,scenario=sc,
                      scenario_id=f"preflight-{i+1}") for i,sc in enumerate(SCENARIOS)]
        seconds=14
    else:
        visits=[(.25+2.3*i,i) for i in range(3)]
        heapq.heapify(visits)
        slots=n
        visits_by_client=Counter()
        while slots:
            at,client=heapq.heappop(visits)
            choices,weights=(SCENARIOS,WEIGHTS) if slots>=2 else (ORDINARY[:2],WEIGHTS[:2])
            label=rng.choices(choices,weights=weights)[0]
            visits_by_client[client]+=1
            actions.append(dict(client=client,offset_s=round(at,3),scenario=label,
                                scenario_id=f"{stage}-{index}-{client+1}-{visits_by_client[client]}"))
            slots-=per_case(label)
            heapq.heappush(visits,(at+rng.uniform(32,89),client))
        seconds=int(actions[-1]["offset_s"])+28
    assert sum(per_case(a["scenario"]) for a in actions)==n
    return dict(seed=seed,duration_seconds=seconds,actions=actions)


def registration():
    batches=[("preflight",0,2026112400,6)]
    batches.extend(("calibration",i,2026112400+i,n) for i,n in enumerate((199,199,198,198),1))
    batches.extend(("holdout",i,2026112410+i,250) for i in range(1,5))
    return {f"{stage}_{i:02}":dict(stage=stage,index=i,connections=n,schedule=plan(stage,i,seed,n))
            for stage,i,seed,n in batches}
