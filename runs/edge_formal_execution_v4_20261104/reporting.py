"""Frozen-selection reporting: exact sample ratios, HT estimates and time sensitivity.

No I/O, model fitting, score thresholds or external-results-driven selection.
Temporal intervals condition on this fixed query sample and are not a proof of
95% coverage under the complete hash sampling design or independent attacks.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import math

import numpy as np

HEADS = ('27', '127', '227', 'ensemble')
ROLES = ('NORMAL', 'HTTP', 'UDP')
HTTP_STRATA = ('SYN_NO_ACK', 'PSH_ACK', 'ACK_ONLY', 'FIN', 'RST', 'OTHER')
BLOCK_NS = 60_000_000_000
INTERVAL_LABEL = 'Conditional temporal sensitivity interval; not full sampling-design 95% coverage'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def fraction(value):
    need(isinstance(value, dict) and type(value.get('numerator')) is int
         and type(value.get('denominator')) is int
         and value['numerator'] > 0 and value['denominator'] > 0, 'POSITIVE_RATIONAL_WEIGHT')
    return Fraction(value['numerator'], value['denominator'])


def group_key(row):
    role = row['source_role']
    need(role in ROLES and isinstance(row.get('capture_id'), str)
         and row['capture_id'], 'POPULATION_GROUP_IDENTITY')
    scenario = row.get('scenario', role)
    need(scenario == role, 'SCENARIO_MUST_MATCH_PINNED_SOURCE_ROLE')
    return role, row['capture_id'], scenario


def population_census(metadata_rows, anchors):
    """Stream every eligible candidate; anchors[(role,capture)] are raw minima.

    metadata_rows come from the sealed full query-candidate metadata spool,
    never the selected-query list. The continuous first..last eligible block
    span includes zero-eligible and zero-selected blocks. Pre-window blocks
    before the first legal candidate are not added to the query population.
    No score or prediction is read by this function.
    """
    groups = {}
    roles = {role: dict(population_count=0, strata=Counter(), protocols=Counter(),
                       tcp_flags=Counter()) for role in ROLES}
    for row in metadata_rows:
        key = group_key(row)
        role, capture, scenario = key
        anchor = anchors.get((role, capture))
        need(type(anchor) is int, 'RAW_CAPTURE_ANCHOR_REQUIRED')
        timestamp = row['timestamp_ns']
        need(type(timestamp) is int and timestamp >= anchor, 'CANDIDATE_BEFORE_RAW_CAPTURE_ANCHOR')
        stratum = row['stratum']
        need(stratum in (('NORMAL',) if role == 'NORMAL' else HTTP_STRATA if role == 'HTTP' else ('UDP',)),
             'UNKNOWN_PINNED_STRATUM')
        group = groups.setdefault(key, dict(source_role=role, capture_id=capture, scenario=scenario,
            anchor_ns=anchor, min_timestamp_ns=timestamp, max_timestamp_ns=timestamp,
            population_count=0, component_counts=Counter(), stratum_counts=Counter(),
            block_population_counts=Counter()))
        group['population_count'] += 1
        # Attack component inclusion probabilities are unavailable: retaining
        # millions of one-packet spoofed five-tuples adds no estimable metric.
        # Normal components are all retained for the registered component mean.
        if role == 'NORMAL':
            group['component_counts'][row['component_id']] += 1
        group['stratum_counts'][stratum] += 1
        group['block_population_counts'][(timestamp-anchor)//BLOCK_NS] += 1
        group['min_timestamp_ns'] = min(group['min_timestamp_ns'], timestamp)
        group['max_timestamp_ns'] = max(group['max_timestamp_ns'], timestamp)
        roles[role]['population_count'] += 1
        roles[role]['strata'][stratum] += 1
        roles[role]['protocols'][str(row['protocol'])] += 1
        if role == 'HTTP':
            flags = int(row['tcp_flags'])
            need(0 <= flags <= 0x1ff, 'INVALID_TCP_FLAGS')
            roles[role]['tcp_flags'][str(flags)] += 1
    for group in groups.values():
        blocks = group['block_population_counts']
        first, last = min(blocks), max(blocks)
        need(last-first <= 10_000_000, 'TEMPORAL_BLOCK_SPAN_LIMIT')
        for block in range(first, last+1):
            blocks[block] += 0
        for field in ('component_counts', 'stratum_counts', 'block_population_counts'):
            group[field] = {str(k): int(v) for k, v in sorted(group[field].items())}
    for role in ROLES:
        for field in ('strata', 'protocols', 'tcp_flags'):
            roles[role][field] = dict(sorted(roles[role][field].items()))
    return dict(schema='EDGE_ELIGIBLE_POPULATION_TEMPORAL_CENSUS_V1',
        input_scope='ALL_SEALED_ELIGIBLE_QUERY_CANDIDATES_NOT_SELECTED_ROWS',
        block_seconds=60, anchor_scope='EXPLICIT_ORIGINAL_CAPTURE_SCENARIO_MINIMUM',
        roles=roles, groups=[groups[key] for key in sorted(groups)], model_scores_used=False)


def _population(population):
    need(population.get('schema') == 'EDGE_ELIGIBLE_POPULATION_TEMPORAL_CENSUS_V1'
         and population.get('block_seconds') == 60, 'TEMPORAL_POPULATION_CENSUS_REQUIRED')
    groups = {}
    for group in population['groups']:
        key = group_key(group)
        need(key not in groups and type(group['anchor_ns']) is int, 'DUPLICATE_POPULATION_GROUP')
        blocks = group['block_population_counts']
        need(blocks and all(str(int(b)) == str(b) and int(b) >= 0
             and type(n) is int and n >= 0 for b, n in blocks.items()), 'POPULATION_BLOCK_COUNTS')
        bi = sorted(map(int, blocks))
        need(bi == list(range(bi[0], bi[-1]+1)) and sum(blocks.values()) > 0,
             'POPULATION_BLOCK_SPAN_OR_MASS')
        need(sum(blocks.values()) == group['population_count'], 'POPULATION_BLOCK_MASS')
        need(sum(group['stratum_counts'].values()) == group['population_count'], 'POPULATION_STRATUM_MASS')
        groups[key] = group
    for role in ROLES:
        value = population['roles'][role]
        need(type(value['population_count']) is int and value['population_count'] >= 0,
             'POPULATION_ROLE_COUNT')
        need(sum(g['population_count'] for key, g in groups.items() if key[0] == role)
             == value['population_count'], 'POPULATION_ROLE_MASS')
        need(sum(value['strata'].values()) == value['population_count'], 'POPULATION_ROLE_STRATA')
        if role == 'HTTP':
            need(sum(value['tcp_flags'].values()) == value['population_count'], 'POPULATION_HTTP_FLAGS')
    return groups


def _weights(rows):
    expansion, component = [], []
    for row in rows:
        weights = row.get('weights', {})
        e = fraction(weights.get('population_expansion_weight'))
        inclusion = fraction(weights.get('row_inclusion_probability'))
        need(inclusion <= 1 and e * inclusion == 1, 'INVERSE_INCLUSION_WEIGHT_MISMATCH')
        expansion.append(float(e))
        component.append(float(fraction(weights['component_metric_weight']))
                         if row['source_role'] == 'NORMAL' else 0.)
    return np.asarray(expansion), np.asarray(component)


def _hierarchical_weights(rows):
    """Existing selected-component hierarchy, not a population attack estimator."""
    weights = np.zeros(len(rows), dtype=np.float64)
    for role in (0, 1):
        indices, branches, leaves = {}, defaultdict(set), Counter()
        for i, row in enumerate(rows):
            if (row['source_role'] != 'NORMAL') != bool(role):
                continue
            key = (row.get('device', row.get('owner', 'PINNED_EDGE_TARGET')),
                   row['capture_id'] if role == 0 else row['source_role'], row['component_id'])
            indices[i] = key
            leaves[key] += 1
            for d in range(len(key)):
                branches[key[:d]].add(key[d])
        for i, key in indices.items():
            weights[i] = 1 / (leaves[key] * math.prod(len(branches[key[:d]]) for d in range(len(key))))
    return weights


def _rate(indices, prediction, expansion, component, hierarchy, population_n=None):
    ix = np.asarray(indices, dtype=np.int64)
    n = len(ix)
    alarms = int(prediction[ix].sum())
    expanded_alarms = math.fsum(expansion[ix][prediction[ix]])
    component_mass = math.fsum(component[ix])
    hierarchy_mass = math.fsum(hierarchy[ix])
    return dict(selected_rows=n, alarm_count=alarms, no_alarm_count=n-alarms,
        exact_selected_sample_alarm_rate=alarms/n if n else None,
        population_count=population_n,
        ht_expanded_alarm_count=expanded_alarms if n and population_n is not None else None,
        ht_population_alarm_estimate=expanded_alarms/population_n if n and population_n else None,
        ht_expanded_sample_count=math.fsum(expansion[ix]) if population_n is not None else None,
        normal_component_metric_weight_mass=component_mass,
        normal_component_equal_alarm_rate=(math.fsum(component[ix][prediction[ix]])/component_mass
                                           if component_mass else None),
        selected_hierarchical_weight_mass=hierarchy_mass,
        selected_hierarchical_alarm_rate=(math.fsum(hierarchy[ix][prediction[ix]])/hierarchy_mass
                                          if hierarchy_mass else None),
        population_component_alarm_rate=('NOT_EVALUABLE_NO_ATTACK_COMPONENT_INCLUSION'
                                         if n and component_mass == 0 else None))


def _safety(indices, rows, raw, candidate, weights):
    groups = {}
    for field, limit in (('device', 1.), ('scenario', 5.)):
        members = defaultdict(list)
        for i in indices:
            if rows[i]['source_role'] != 'NORMAL':
                value = rows[i]['source_role'] if field == 'scenario' else rows[i].get(
                    'device', rows[i].get('owner', 'PINNED_EDGE_TARGET'))
                members[str(value)].append(i)
        for name, values in sorted(members.items()):
            ix = np.asarray(values, dtype=np.int64)
            mass = math.fsum(weights[ix])
            need(mass > 0, 'ZERO_ATTACK_SAFETY_WEIGHT')
            withdrawn = raw[ix] & ~candidate[ix]
            recall = math.fsum(weights[ix][raw[ix]]) / mass
            loss = 100 * math.fsum(weights[ix][withdrawn]) / mass
            failures = (['WITHDRAWAL_BUDGET'] if loss > limit else [])
            if recall < .99 and withdrawn.any():
                failures.append('LOW_RAW_RECALL_ANY_WITHDRAWAL')
            groups[field+':'+name] = dict(rows=len(ix), raw_recall=recall,
                withdrawn_raw_TP=int(withdrawn.sum()), weighted_loss_pp=loss,
                budget_pp=limit, status='FAIL' if failures else 'PASS', failures=failures)
    return dict(status=('NOT_EVALUABLE' if not groups else 'FAIL'
                if any(g['status'] == 'FAIL' for g in groups.values()) else 'PASS'),
                groups=groups, independent_official_event_gate='NOT_EVALUABLE_NO_EVENT_LEDGER')


def temporal_sensitivity(rows, prediction, expansion, groups, role, *, repetitions=2000, seed=20261103):
    """Resample population time blocks within every capture/scenario group.

    Point estimates retain known full N. Replicates resample each block's HT
    alarm numerator and exact eligible-population count denominator together.
    Empty-selected population blocks have zero estimated numerator, and remain
    in the resampling frame. No packet or synthetic attack-event bootstrap.
    """
    need(type(repetitions) is int and repetitions > 0, 'POSITIVE_REPETITIONS')
    need(type(seed) is int, 'INTEGER_SEED')
    rng = np.random.default_rng(seed)
    numerator = np.zeros(repetitions, dtype=np.float64)
    denominator = np.zeros(repetitions, dtype=np.float64)
    facts = []
    members = defaultdict(list)
    for i, row in enumerate(rows):
        if row['source_role'] == role:
            members[group_key(row)].append(i)
    for key in sorted(key for key in groups if key[0] == role):
        group = groups[key]
        blocks = sorted(map(int, group['block_population_counts']))
        mapping = {block: i for i, block in enumerate(blocks)}
        counts = np.asarray([group['block_population_counts'][str(block)] for block in blocks], dtype=np.float64)
        errors = np.zeros(len(blocks), dtype=np.float64)
        selected = np.zeros(len(blocks), dtype=np.int64)
        for i in members[key]:
            block = (rows[i]['timestamp_ns']-group['anchor_ns'])//BLOCK_NS
            need(block in mapping, 'SELECTED_ROW_OUTSIDE_POPULATION_BLOCK')
            index = mapping[block]
            selected[index] += 1
            if prediction[i]:
                errors[index] += expansion[i]
        # Chunking bounds memory at 128 * population blocks; same RNG draw order.
        for start in range(0, repetitions, 128):
            stop = min(start+128, repetitions)
            draws = rng.integers(0, len(blocks), size=(stop-start, len(blocks)))
            numerator[start:stop] += errors[draws].sum(axis=1)
            denominator[start:stop] += counts[draws].sum(axis=1)
        facts.append(dict(source_role=key[0], capture_id=key[1], scenario=key[2],
            anchor_ns=group['anchor_ns'], eligible_population_blocks=len(blocks),
            zero_eligible_population_blocks=int((counts == 0).sum()),
            selected_blocks=int((selected > 0).sum()), zero_selected_population_blocks=int((selected == 0).sum())))
    valid = denominator > 0
    sampled_rows = sum(map(len, members.values()))
    if valid.any() and sampled_rows:
        values = numerator[valid]/denominator[valid]
        interval = [float(x) for x in np.percentile(values, [2.5, 97.5])]
    else:
        interval = None
    return dict(label=INTERVAL_LABEL, block_seconds=60, seed=seed, repetitions=repetitions,
        status='SAMPLED' if sampled_rows else 'NOT_SAMPLED',
        interval_2_5_97_5=interval, valid_repetitions=int(valid.sum()) if sampled_rows else 0,
        positive_denominator_repetitions=int(valid.sum()),
        zero_denominator_repetitions=int((~valid).sum()),
        capture_scenario_groups=facts,
        denominator='Resampled exact eligible-population block counts; point HT estimate uses fixed known N',
        selected_zero_blocks_retained=True, no_independent_packet_or_event_CI=True)


def summarise(rows, predictions, population, *, prediction_uids, raw_name='RAW',
              independent_methods=('STANDARD_KNN5',), repetitions=2000, seed=20261103):
    """Report one already frozen ordered query table and all methods together."""
    need(isinstance(predictions, dict) and raw_name in predictions, 'RAW_PREDICTION_REQUIRED')
    uids = [row['uid'] for row in rows]
    need(len(uids) == len(set(uids)), 'DUPLICATE_QUERY_UID')
    need(set(prediction_uids) == set(predictions) and all(list(prediction_uids[name]) == uids
         for name in predictions), 'ORDERED_QUERY_UID_JOIN')
    need(all(row.get('use') == 'QUERY' for row in rows), 'REFERENCE_OR_UNSELECTED_ROW_IN_QUERY_DENOMINATOR')
    arrays = {}
    for name, value in predictions.items():
        a = np.asarray(value)
        need(a.dtype == np.bool_ and a.shape == (len(rows), 4), 'ORDERED_FOUR_HEAD_BOOL_PREDICTIONS')
        arrays[name] = a
    groups = _population(population)
    for row in rows:
        key = group_key(row)
        need(key in groups and type(row['timestamp_ns']) is int, 'QUERY_POPULATION_GROUP_OR_CLOCK')
        group = groups[key]
        block = (row['timestamp_ns']-group['anchor_ns'])//BLOCK_NS
        need(str(block) in group['block_population_counts'], 'SELECTED_ROW_OUTSIDE_POPULATION_BLOCK')
        need(group['block_population_counts'][str(block)] > 0, 'SELECTED_ROW_IN_ZERO_POPULATION_BLOCK')
        if row['source_role'] == 'HTTP':
            need(type(row.get('tcp_flags')) is int and 0 <= row['tcp_flags'] <= 0x1ff,
                 'QUERY_HTTP_FLAGS_REQUIRED')
    expansion, component = _weights(rows)
    hierarchy = _hierarchical_weights(rows)
    all_indices = list(range(len(rows)))
    partitions = {}
    for role in ROLES:
        ix = [i for i, row in enumerate(rows) if row['source_role'] == role]
        need(len(ix) <= population['roles'][role]['population_count'], 'SELECTED_COUNT_EXCEEDS_POPULATION')
        partitions[role] = ix
    raw = arrays[raw_name]
    reports = {}
    for method, decisions in arrays.items():
        independent = method in independent_methods
        if not independent:
            need(not np.any(~raw & decisions), 'SUPPRESSION_METHOD_ADDS_RAW_ALARM')
        heads = {}
        for j, head in enumerate(HEADS):
            roles = {}
            for role in ROLES:
                ix = partitions[role]
                spec = population['roles'][role]
                metric = _rate(ix, decisions[:, j], expansion, component, hierarchy, spec['population_count'])
                metric['metric'] = 'FPR' if role == 'NORMAL' else 'ATTACK_ASSOCIATED_RECALL'
                metric['false_positive_count' if role == 'NORMAL' else 'false_negative_count'] = (
                    metric['alarm_count'] if role == 'NORMAL' else metric['no_alarm_count'])
                metric['sampling_status'] = 'SAMPLED' if ix else 'NOT_SAMPLED'
                metric['unsampled_population_rows'] = spec['population_count']-len(ix)
                metric['unselected_policy'] = 'NOT_SAMPLED_NOT_CORRECT_NEGATIVE'
                metric['strata'] = {}
                strata = ('NORMAL',) if role == 'NORMAL' else HTTP_STRATA if role == 'HTTP' else ('UDP',)
                for stratum in strata:
                    sx = [i for i in ix if rows[i]['stratum'] == stratum]
                    metric['strata'][stratum] = _rate(sx, decisions[:, j], expansion, component,
                        hierarchy, spec['strata'].get(stratum, 0))
                if role == 'HTTP':
                    # Overlapping header audit subsets, separate from the
                    # mutually exclusive sampling strata. Do not infer payload
                    # or HTTP semantics from PSH or ACK flags.
                    predicates = dict(
                        SYN_NO_ACK=lambda f: bool(f & 0x02) and not bool(f & 0x10),
                        ACK_NO_SYN=lambda f: bool(f & 0x10) and not bool(f & 0x02),
                        ACK_ONLY=lambda f: f == 0x10,
                        PSH_ACK=lambda f: f == 0x18,
                        OUTSIDE_SYN_GUARD=lambda f: not (bool(f & 0x02) and not bool(f & 0x10)))
                    metric['header_audit_subsets'] = {}
                    for name, predicate in predicates.items():
                        sx = [i for i in ix if predicate(rows[i]['tcp_flags'])]
                        count = sum(n for f, n in spec['tcp_flags'].items() if predicate(int(f)))
                        metric['header_audit_subsets'][name] = _rate(sx, decisions[:, j],
                            expansion, component, hierarchy, count)
                    for name in ('HTTP_GET', 'HTTP_PAYLOAD'):
                        metric['header_audit_subsets'][name] = dict(status='NOT_EVALUABLE',
                            reason='Frozen selected metadata has no HTTP method or payload-length fields; PSH is not a substitute')
                metric['conditional_time_sensitivity'] = temporal_sensitivity(rows, decisions[:, j], expansion,
                    groups, role, repetitions=repetitions, seed=seed)
                roles[role] = metric
            segment_protocol = {}
            for capture, protocol in sorted({(r['capture_id'], r['protocol']) for r in rows}):
                ix = [i for i, r in enumerate(rows) if r['capture_id'] == capture and r['protocol'] == protocol]
                segment_protocol[capture+':'+str(protocol)] = _rate(ix, decisions[:, j], expansion, component, hierarchy)
            if independent:
                attack = np.asarray([r['source_role'] != 'NORMAL' for r in rows])
                safety = dict(status='DESCRIPTIVE_INDEPENDENT_DETECTOR', suppression_only_gate_applies=False,
                    withdrawn_raw_TP=int(np.sum(attack & raw[:, j] & ~decisions[:, j])),
                    added_raw_negative_alarms=int(np.sum(~raw[:, j] & decisions[:, j])))
            else:
                safety = _safety(all_indices, rows, raw[:, j], decisions[:, j], hierarchy)
            heads[head] = dict(roles=roles, segment_protocol_selected_descriptive=segment_protocol,
                              raw_cumulative_safety=safety)
        reports[method] = dict(heads=heads, independent_detector=independent,
            score_identity=('One distance score at four matched source working points' if independent
                            else 'Frozen three head scores plus ensemble'))
    return dict(schema='EDGE_FROZEN_QUERY_REPORT_V1', query_rows=len(rows), methods=reports,
        ordered_query_uids=uids, views=dict(post_window_primary='EVALUATED_SELECTED_QUERIES',
            full=dict(normal='NOT_EVALUABLE_POSTWINDOW_ONLY_SELECTION',
                      attack='SAME_ELIGIBLE_ATTACK_POPULATION_AS_PRIMARY')),
        unselected_population_rows='NOT_SAMPLED', references_in_query_denominator=0,
        external_quality_used_for_selection=False, ht_renormalized=False, ht_clamped=False,
        uncertainty=INTERVAL_LABEL, independent_attack_event_recall='NOT_EVALUABLE_NO_EVENT_LEDGER')
