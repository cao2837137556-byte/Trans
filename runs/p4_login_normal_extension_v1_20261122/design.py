"""Fixed sampling design for an expanded normal-login holdout."""

from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
CALIBRATION = HERE.parent / "p4_login_calibration_v1_20261122"
sys.path.insert(0, str(CALIBRATION))

from plans import SCENARIOS, WEIGHTS
from schedule import ORDINARY, RECOVER

CALIBRATION_ID = "calibration_20261122_ad0fc3"
PRIOR_CONNECTIONS = 194
TARGET_CONNECTIONS = 1_000
SEEDS = (2026112210, 2026112211, 2026112212, 2026112213, 2026112214)
SECONDS_PER_BATCH = 3_900


def schedule(batch):
    seed = SEEDS[batch]
    actions = []
    if batch == 0:
        for index, scenario in enumerate(SCENARIOS):
            actions.append(dict(client=index % 3, offset_s=0.25 + index * 2.3,
                                scenario=scenario, scenario_id=f"preflight-{index + 1}"))
        return dict(seed=seed, duration_seconds=14, actions=actions)

    rng = random.Random(seed)
    for client in range(3):
        at = 0.25 + client * 2.3
        index = 0
        while at < SECONDS_PER_BATCH - 27:
            scenario, = rng.choices(SCENARIOS, weights=WEIGHTS)
            index += 1
            actions.append(dict(client=client, offset_s=round(at, 3), scenario=scenario,
                                scenario_id=f"holdout-{batch}-{client + 1}-{index}"))
            at += rng.uniform(32, 89)
    return dict(seed=seed, duration_seconds=SECONDS_PER_BATCH,
                actions=sorted(actions, key=lambda action: action["offset_s"]))


def expected_connections(plan):
    return sum(2 if action["scenario"] in (ORDINARY[2], RECOVER) else 1
               for action in plan["actions"])
