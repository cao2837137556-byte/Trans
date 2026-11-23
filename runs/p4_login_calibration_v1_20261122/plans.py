"""Choose two independently seeded daily captures at the enrollment rhythm."""
import random

from sources import FORMAL
from schedule import ORDINARY, RECOVER

SECONDS=3600
SEEDS={"calibration":2026112201,"holdout":2026112202}
SCENARIOS=(*ORDINARY,RECOVER)
WEIGHTS=(76,12,5,7)


def normal_plan(stage):
    rng=random.Random(SEEDS[stage])
    actions=[]
    for client in range(3):
        at=.25+client*2.3
        n=0
        while at<SECONDS-27:
            label=rng.choices(SCENARIOS,weights=WEIGHTS)[0]
            n+=1
            actions.append(dict(client=client,offset_s=round(at,3),scenario=label,
                                scenario_id=f"{stage}-{client+1}-{n}"))
            at+=rng.uniform(32,89)
    return dict(seed=SEEDS[stage],duration_seconds=SECONDS,actions=sorted(actions,key=lambda a:a["offset_s"]))
