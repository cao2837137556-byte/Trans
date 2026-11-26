"""Preregister the independent WSL legitimate reconnect batches."""
import itertools
import math
import random

RATES = (3, 5, 6, 7, 8)
BATCH_CONNECTIONS = 40
PREFLIGHT = "preflight"
SEED = 2026112603
SILENCE_S = 62
HANDSHAKE_CUT = 4
STAGE = "holdout"
REFERENCE = "formal_20261122_402788"
RANK5 = "rank5_20261124_022354"
ATTACK = "attack_eval_20261126"
BENCHMARK_SAMPLES = 18
BENCHMARK_WARMUP = 3


def batch(rate, repeat, seed, preflight=False):
    rng = random.Random(seed)
    key = PREFLIGHT if preflight else f"rate{rate:02d}_batch{repeat}"
    # Give each client the 14-connection position once at each rate.
    sizes = [5]*3 if preflight else [13 + (i == repeat-1) for i in range(3)]
    actions = []
    for client, size in enumerate(sizes):
        shift = round(5.5 + client*.45 + rng.uniform(0, .20), 3)
        offsets = [round((i+.5)*60/rate, 6) for i in range(size)]
        actions.append(dict(client=client, scenario="burst_reconnect",
                            scenario_id=f"{key}-c{client+1}", scheduled_rate=rate,
                            offset_s=shift, within_minute_s=offsets))
    duration = math.ceil(max(a["offset_s"] + max(a["within_minute_s"][-1]+3, (size//rate)*60+.5)
                             for a,size in zip(actions,sizes,strict=True)))
    return dict(key=key, scheduled_rate=rate, replicate=repeat,
                connections=sum(sizes), per_client=sizes,
                schedule=dict(seed=seed, actions=actions, duration_seconds=duration))


def registration():
    order = list(itertools.product(RATES, (1, 2, 3)))
    rng = random.Random(SEED)
    rng.shuffle(order)
    formal = [batch(rate, rep, rng.randrange(2**32)) for rate, rep in order]
    preflight = batch(8, 0, SEED+1, preflight=True)
    assert sum(row["connections"] for row in formal)==600
    assert all(row["connections"]==BATCH_CONNECTIONS for row in formal)
    return dict(root_seed=SEED, rates=list(RATES), batches_per_rate=3,
                batch_connections=BATCH_CONNECTIONS, formal_connections=600,
                min_planned_silence_s=SILENCE_S, preflight=preflight, formal=formal)
