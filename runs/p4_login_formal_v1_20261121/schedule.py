"""Fixed sampling schedules for enrollment and the independent normal assessment."""
import random

SEEDS = {"enrollment":2026112101,"evaluation":2026112102}
ORDINARY = ("successful_login","mistake_then_retry","cross_connection_retry")
BURST = "burst_reconnect"
RECOVER = "disconnect_then_reconnect"
RATES = (1,3,5,8)


def plan_enrollment(window=7200):
    rng = random.Random(SEEDS["enrollment"])
    actions = []
    for client in range(3):
        at = .25+client*2.3
        n = 0
        while at < window-27:
            label = rng.choices([*ORDINARY,RECOVER],weights=(76,12,5,7))[0]
            n += 1
            actions.append(dict(client=client,offset_s=round(at,3),scenario=label,
                                scenario_id=f"enr-{client+1}-{n}"))
            at += rng.uniform(32,89)
    for delay in range(4,185,9):
        actions.append(dict(client=0,offset_s=window+delay,scenario=ORDINARY[0],
                            scenario_id=f"enr-boundary-{delay}",boundary_probe=True))
    return dict(seed=SEEDS["enrollment"],window_seconds=window,actions=sorted(actions,key=lambda a:a["offset_s"]))


def plan_evaluation():
    rng=random.Random(SEEDS["evaluation"])
    deck=[(client,scenario) for client in range(3) for scenario in ORDINARY for _ in range(12)]
    rng.shuffle(deck)
    at=1.
    actions=[]
    for i,(client,scenario) in enumerate(deck,1):
        actions.append(dict(client=client,offset_s=round(at,3),scenario=scenario,scenario_id=f"eval-{i}"))
        at+=rng.uniform(1.7,3.5)
    at+=65
    minutes=[(client,rate) for client in range(3) for rate in RATES]
    rng.shuffle(minutes)
    for i,(client,rate) in enumerate(minutes,1):
        times=[round(4+(j+.5)*48/rate+rng.uniform(-.3,.3),3) for j in range(rate)]
        actions.append(dict(client=client,offset_s=round(at,3),scenario=BURST,
                     scenario_id=f"minute-{i}",scheduled_rate=rate,within_minute_s=times))
        at+=rng.uniform(76,83)
    return dict(seed=SEEDS["evaluation"],ordinary_repeats_per_client=12,minute_blocks=len(minutes),
                rates=list(RATES),duration_seconds=round(at,3),actions=actions)
