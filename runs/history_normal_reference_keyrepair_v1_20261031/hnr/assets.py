"""Pinned read-only assets; A/B datasets are loaded only by terminal evaluation.

Importing this module performs no model or scientific input reads. Metadata,
arrays and saved logits retain the exact UID checks in the original runner.
"""
from pathlib import Path
import importlib.util
import sys

import numpy as np

from .common import PACKAGE, ROOT, HEIM, read, require, sha


def helpers():
    """Reuse the pinned matrix's UID joins and original metric hierarchy."""
    directory = ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src'
    name = '_history_original_matrix'
    if name not in sys.modules:
        old = sys.path[:]
        try:
            sys.path.insert(0, str(directory))
            spec = importlib.util.spec_from_file_location(name, directory / 'matrix.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            require(Path(module.metrics.__file__).resolve() == (directory / 'metrics.py').resolve(),
                    'ORIGINAL_METRIC_MODULE_COLLISION')
        finally:
            sys.path[:] = old
    return sys.modules[name]


def joined(rows, e3, q14, **extra):
    ids = [r['uid'] for r in rows]
    return dict(rows=list(rows), e3=e3, q14=q14, feature_uids=ids, q_uids=ids, **extra)


class AssetInputs:
    def __init__(self, root=ROOT, manifest=None):
        self.root = Path(root).resolve()
        self.spec = read(manifest or PACKAGE / 'config/ASSETS.json')
        require(self.spec['schema'] == 'history-normal-reference-assets-v1', 'ASSET_SCHEMA')
        self.inputs = helpers().Inputs(self.root)

    def calibration(self):
        spec = self.spec['calibration']
        values = {name: self.inputs.json(spec[name]) for name in ('geometry', 'cuts', 'scales')}
        with np.load(self.inputs.pin(spec['normalizer']), allow_pickle=False) as saved:
            values['normalizer'] = (saved['mean'].copy(), saved['scale'].copy())
        cuts = values['cuts']
        require(cuts['seeds'] == [27, 127, 227] and cuts['moved'] is False, 'FROZEN_CUTS')
        require(cuts['cuts'] == [-23.066728591918945, -19.736963272094727, -20.966501235961914]
                and cuts['ensemble_cut'] == -22.66365687052409, 'FROZEN_OPERATING_POINT')
        return values

    def dense(self, pool):
        return self.inputs.dataset(self.spec['pools'][pool]['dense_bank'])

    def a_history(self):
        spec = self.spec['a_history']
        rows = self.inputs.rows(spec['rows'])
        with np.load(self.inputs.pin(spec['arrays']), allow_pickle=False) as saved:
            require(saved['uid'].tolist() == [r['uid'] for r in rows], 'A_HISTORY_UID_JOIN')
            ix = np.asarray([i for i, r in enumerate(rows) if r['device'] == HEIM['device']], dtype=np.int64)
            require(len(ix) == spec['expected_rows'] == 11, 'A_REUSE_11_COUNT')
            selected = [rows[int(i)] for i in ix]
            require(all(r['partition'] == HEIM['partition'] and r['owner'] == HEIM['owner']
                        and r['use'] == 'REFERENCE' and r['label'] == 0 for r in selected), 'A_REUSE_11_ROLE')
            require(sum(r['protocol'] == 6 for r in selected) == 1 and
                    sum(r['protocol'] == 17 for r in selected) == 10, 'A_REUSE_11_PROTOCOL')
            return joined(selected, saved['e3'][ix].copy(), saved['q14'][ix].copy())

    def queries(self, pool):
        return self.inputs.dataset(self.spec['pools'][pool]['query'], logits=True)

    def baseline(self, pool, uids):
        spec = self.spec['pools'][pool]
        with np.load(self.inputs.pin(spec['baseline_decisions']), allow_pickle=False) as saved:
            require(saved['uid'].tolist() == list(uids), 'BASELINE_UID_JOIN')
            require(float(saved['selected_lambda']) == .25, 'BASELINE_LAMBDA')
            arrays = {k: saved[k].copy() for k in ('support', 'eligible', 'base', 'corrected', 'raw_logits')}
        return arrays, self.inputs.json(spec['baseline_result'])

    def immutable(self):
        self.inputs.immutable()

    def preflight(self):
        """Hash/size only; no NPZ payload, query, head, or PCAP decoding."""
        specs = []
        def collect(x):
            if isinstance(x, dict):
                if 'path' in x and 'sha256' in x:
                    specs.append(x)
                else:
                    for item in x.values(): collect(item)
            elif isinstance(x, list):
                for item in x: collect(item)
        collect(self.spec)
        seen = {}
        for spec in specs:
            path = self.inputs.pin(spec)
            if 'bytes' in spec:
                require(path.stat().st_size == spec['bytes'], 'ASSET_SIZE:' + str(path))
            seen[str(path)] = spec['sha256']
        return dict(status='INPUT_PINS_ACCEPTED', files=len(seen), pins=seen,
                    model_forwards=0, new_scores=0, distances=0, raw_decodes=0)


def load_assets(root=ROOT, manifest=None):
    return AssetInputs(root, manifest)


def score_dev(queries, assets, frozen=None, runtime=None):
    """Frozen original QUERY_TAIL inference for historical DEV only; no fitting.

    Six-head parent material is preserved. The main registered operating point
    consumes its three QUERY_TAIL endpoints, just as the saved A/B head logits.
    """
    import torch
    import query_tail_core_v2 as k
    import constrained_onboarding_query_tail_adapter_v2 as adapter
    import constrained_onboarding_core_v3 as core
    frozen = assets.calibration() if frozen is None else frozen
    rows = queries['rows']
    require(rows and all(r['label'] == 0 and r['use'] != 'REFERENCE' for r in rows), 'DEV_NORMAL_QUERIES_ONLY')
    require(len(rows) <= 12288, 'DEV_TOTAL_CAP')
    ids = [r['uid'] for r in rows]
    core._joined(rows, queries['e3'], queries['q14'], queries.get('feature_uids', ids), queries.get('q_uids', ids))
    design = assets.inputs.json(assets.spec['heads']['design'])
    require(sha(assets.inputs.pin(assets.spec['heads']['design'])) == k.DESIGN_SHA, 'HEAD_DESIGN_PIN')
    columns = []
    for seed in core.SEEDS:
        pins = assets.spec['heads']['endpoints'][str(seed)]
        endpoint = assets.inputs.pin(pins['endpoint.json'])
        head = assets.inputs.pin(pins['head.npz'])
        require(head.parent == endpoint.parent, 'HEAD_ENDPOINT_DIRECTORY')
        adapter._endpoint(endpoint.parent, 'QUERY_TAIL', seed, design, frozen['normalizer'])
        model = k.classifier(seed, 782)
        with np.load(head, allow_pickle=False) as saved:
            require(set(saved.files) == set(model.state_dict()), 'HEAD_KEYS')
            model.load_state_dict({key: torch.from_numpy(saved[key].copy()) for key in saved.files})
        model.eval().requires_grad_(False)
        class Progress:
            def tick(self, done, total):
                if runtime is not None:
                    runtime.update('DEV_HEAD_SCORING', seed=seed, completed=done, total=total)
        columns.append(k.scores(model, queries['e3'], queries['q14'], np.arange(len(rows)),
                                frozen['normalizer'], 782, Progress()))
        del model
    result = dict(queries)
    result['logits'] = np.column_stack(columns).astype(np.float64)
    return result
