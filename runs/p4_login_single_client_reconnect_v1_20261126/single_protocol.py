"""Fixed single-client rotation, pacing and preflight."""
import math
import random

RATES = (3,5,6,7,8)
CLIENTS = (1,2,3)
SEED = 2026112607
JITTER = .35
QUIET_SECONDS = 62
REFERENCE = "formal_20261122_402788"
SYNC_ROOT = "reconnect_stress_20261126_000811"
STAGE = "holdout"


def batch(client,rate,n,seed,preflight=False):
    key = "preflight" if preflight else f"rate{rate:02d}_client{client}"
    rng = random.Random(seed)
    jitters = [round(rng.uniform(-JITTER,JITTER),6) for _ in range(n)]
    slots = [round((i+.5)*60/rate+delta,6) for i,delta in enumerate(jitters)]
    start = 5.5
    end = math.ceil(start+max(slots[-1]+3,(n//rate)*60+1))
    action = dict(client=client-1,scenario="burst_reconnect",scenario_id=f"{key}-c{client}",
                  scheduled_rate=rate,offset_s=start,within_minute_s=slots)
    return dict(key=key,client=client,scheduled_rate=rate,connections=n,jitter_s=jitters,
                schedule=dict(seed=seed,actions=[action],duration_seconds=end))


def registration():
    rng = random.Random(SEED)
    schedules = {}
    for client in CLIENTS:
        rates = list(RATES)
        rng.shuffle(rates)
        schedules[client] = rates
    formal = [batch(client,schedules[client][i],40,rng.getrandbits(32))
              for i in range(len(RATES)) for client in CLIENTS]
    keys = {(b["client"],b["scheduled_rate"]) for b in formal}
    assert keys=={(c,r) for c in CLIENTS for r in RATES}
    assert sum(b["connections"] for b in formal)==600
    return dict(root_seed=SEED,client_order=list(CLIENTS),rates=list(RATES),
                jitter=dict(distribution="uniform",min_s=-JITTER,max_s=JITTER,
                            rule="round((ordinal - 0.5) * 60 / rate + jitter, 6) s"),
                formal_connections=600,batch_connections=40,min_planned_silence_s=QUIET_SECONDS,
                preflight=batch(2,8,8,SEED+1,preflight=True),formal=formal)
