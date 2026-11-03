"""Metadata-only Edge query selection; no model, feature, label-score imports.

Selected packets remain physical query endpoints. This module never removes
unselected packets from causal context and does not deduplicate model inputs.
All quota/rank decisions use exact integers and fixed public hash salts.
"""
from __future__ import annotations

import hashlib
import heapq
from fractions import Fraction

NORMAL_SALT = 'edge-normal-query-v1-20261103'
ATTACK_SALT = 'edge-attack-query-v1-20261103'
HTTP_STRATA = ('SYN_NO_ACK', 'PSH_ACK', 'ACK_ONLY', 'FIN', 'RST', 'OTHER')
B_QUOTA_BRANCH = 'B_RESIDUAL_CAPACITY'
FALLBACK_BRANCH = 'HASH_COMPONENT_FALLBACK'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _counts(counts):
    _require(isinstance(counts, dict) and bool(counts), 'EMPTY_POPULATION')
    _require(all(isinstance(g, str) and g and type(n) is int and n > 0
                 for g, n in counts.items()), 'INVALID_POPULATION_COUNTS')
    return sum(counts.values()), len(counts)


def hash_rank(salt, value):
    """Exact SHA256(salt|identifier), with no normalization or hidden seed."""
    _require(isinstance(salt, str) and isinstance(value, str), 'HASH_INPUT_TYPE')
    return hashlib.sha256((salt + '|' + value).encode('utf-8')).hexdigest()


def http_stratum(flags):
    """Mutually exclusive observed-header strata, in a pinned priority order.

    SYN_NO_ACK uses the protocol predicate SYN=1, ACK=0. The remaining classes
    are exact values observed in the sealed HTTP population: PSH+ACK 0x18,
    ACK-only 0x10, FIN+ACK/FIN+PSH+ACK 0x11/0x19 and RST-only 0x04. Any other
    future flag value is OTHER, except the initial SYN_NO_ACK predicate.
    """
    _require(type(flags) is int and 0 <= flags <= 0x1ff, 'INVALID_TCP_FLAGS')
    if flags & 0x02 and not flags & 0x10:
        return 'SYN_NO_ACK'
    if flags == 0x18:
        return 'PSH_ACK'
    if flags == 0x10:
        return 'ACK_ONLY'
    if flags in (0x11, 0x19):
        return 'FIN'
    if flags == 0x04:
        return 'RST'
    return 'OTHER'


def normal_plan(counts, budget=20000, salt=NORMAL_SALT):
    """B residual-capacity quotas, with the predeclared component fallback.

    The fallback selects K components by component hash and one hash-ranked
    query per selected component. It is a two-stage selection, so population
    expansion weights must include C/K; see normal_weights.
    """
    total, components = _counts(counts)
    _require(type(budget) is int and budget > 0, 'INVALID_NORMAL_BUDGET')
    k = min(budget, total)
    if components > k:
        chosen = sorted(counts, key=lambda g: (hash_rank(salt, g), g))[:k]
        quotas = {g: 1 for g in sorted(chosen)}
        branch = FALLBACK_BRANCH
    else:
        branch = B_QUOTA_BRANCH
        if total == components:
            quotas = dict(sorted(counts.items()))
        else:
            remaining, denominator = k - components, total - components
            quotas = {g: 1 + remaining * (n - 1) // denominator
                      for g, n in counts.items()}
            order = sorted(counts, key=lambda g:
                           (-(remaining * (counts[g] - 1) % denominator), g))
            for g in order[:k - sum(quotas.values())]:
                quotas[g] += 1
            quotas = dict(sorted(quotas.items()))
    _require(sum(quotas.values()) == k and
             all(1 <= m <= counts[g] for g, m in quotas.items()), 'NORMAL_QUOTA_DRIFT')
    return dict(branch=branch, population_count=total, component_count=components,
                requested_budget=budget, effective_budget=k,
                selected_component_count=len(quotas), salt=salt, quotas=quotas,
                row_rank='(SHA256(salt|uid),uid)',
                component_rank='(SHA256(salt|component_id),component_id)')


def attack_plan(counts, budget=20000, order=HTTP_STRATA, minimum=1000):
    """Scene quota, proportional exact largest remainders, then stratum floors.

    Largest-remainder ties use the explicit fixed stratum order. After raising
    each nonempty stratum to min(N_h, minimum), excess seats are removed one
    at a time from the currently largest donor quota that remains above its
    floor, ties again by fixed order. Thus the phrase 'largest layer' has one
    reproducible interpretation and no population/float rounding ambiguity.
    Empty strata may be present as zero for reporting and receive zero seats.
    """
    _require(isinstance(counts, dict) and counts and
             all(isinstance(h, str) and h and type(n) is int and n >= 0
                 for h, n in counts.items()), 'INVALID_ATTACK_COUNTS')
    _require(type(budget) is int and budget > 0 and
             type(minimum) is int and minimum >= 0, 'INVALID_ATTACK_BUDGET')
    order = tuple(order)
    _require(len(set(order)) == len(order) and set(counts) <= set(order),
             'UNKNOWN_OR_DUPLICATE_STRATUM')
    total = sum(counts.values())
    _require(total > 0, 'EMPTY_ATTACK_POPULATION')
    k = min(budget, total)
    floors = {h: min(counts.get(h, 0), minimum) for h in order}
    _require(sum(floors.values()) <= k, 'STRATUM_FLOORS_EXCEED_BUDGET')
    proportional = {h: k * counts.get(h, 0) // total for h in order}
    tie_index = {h: i for i, h in enumerate(order)}
    remainder_order = sorted(order, key=lambda h:
                             (-(k * counts.get(h, 0) % total), tie_index[h]))
    for h in remainder_order[:k - sum(proportional.values())]:
        proportional[h] += 1
    quotas = {h: max(proportional[h], floors[h]) for h in order}
    excess = sum(quotas.values()) - k
    donors = [(-quotas[h], tie_index[h], h) for h in order
              if quotas[h] > floors[h]]
    heapq.heapify(donors)
    for _ in range(excess):
        _require(bool(donors), 'STRATUM_FLOORS_INFEASIBLE')
        _, index, h = heapq.heappop(donors)
        quotas[h] -= 1
        if quotas[h] > floors[h]:
            heapq.heappush(donors, (-quotas[h], index, h))
    _require(sum(quotas.values()) == k and
             all(floors[h] <= quotas[h] <= counts.get(h, 0) for h in order),
             'ATTACK_QUOTA_DRIFT')
    return dict(population_count=total, requested_budget=budget, effective_budget=k,
                stratum_order=list(order), proportional_quotas=proportional,
                minimum_per_nonempty_stratum=minimum, floors=floors, quotas=quotas,
                salt=ATTACK_SALT, row_rank='(SHA256(salt|uid),uid)',
                floor_donor_rule='Largest current quota above floor; fixed stratum-order ties')


def _ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def normal_weights(n_g, m_g, component_count, selected_component_count, branch):
    """Exact rational coefficients per selected row under hash sampling.

    Hash ranks are interpreted as a fixed pseudorandom sampling design. These
    are design expansion coefficients, not proof that network packets are
    independent. Population estimates divide expanded error sums by the known
    full population N, even when the expanded selected count differs from N.
    """
    _require(all(type(n) is int and n > 0 for n in
                 (n_g, m_g, component_count, selected_component_count)),
             'INVALID_WEIGHT_COUNTS')
    _require(m_g <= n_g and selected_component_count <= component_count,
             'WEIGHT_COUNTS_OUT_OF_RANGE')
    if branch == B_QUOTA_BRANCH:
        _require(selected_component_count == component_count, 'B_COMPONENTS_MISSING')
        inclusion = Fraction(m_g, n_g)
        component = Fraction(1, component_count * m_g)
    elif branch == FALLBACK_BRANCH:
        _require(m_g == 1 and selected_component_count < component_count,
                 'FALLBACK_NOT_ONE_PER_COMPONENT')
        inclusion = Fraction(selected_component_count, component_count * n_g)
        component = Fraction(1, selected_component_count)
    else:
        raise ValueError('UNKNOWN_NORMAL_BRANCH')
    return dict(row_inclusion_probability=_ratio(inclusion),
                population_expansion_weight=_ratio(1 / inclusion),
                component_metric_weight=_ratio(component))


def attack_weights(n_h, m_h):
    _require(type(n_h) is int and type(m_h) is int and 0 < m_h <= n_h,
             'INVALID_ATTACK_WEIGHT_COUNTS')
    inclusion = Fraction(m_h, n_h)
    return dict(row_inclusion_probability=_ratio(inclusion),
                population_expansion_weight=_ratio(1 / inclusion))
