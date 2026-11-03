"""Explicitly import frozen historical helpers without launching old runners."""
import importlib
import importlib.util
from pathlib import Path
import sys

from .common import ROOT, require


def _file_module(name, path, package=False):
    path = Path(path).resolve()
    if name in sys.modules:
        module = sys.modules[name]
        require(Path(module.__file__).resolve() == path, 'LEGACY_MODULE_COLLISION:' + name)
        return module
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def get_core(root=None):
    root = Path(root or ROOT).resolve()
    old = sys.path.copy()
    try:
        sys.path.insert(0, str(root / 'repo/ood'))
        for name in ('legacy_qref_common_v1', 'legacy_qref_data_v1', 'indexed_features_v1',
                     'causal_reference_overlap_v1', 'constrained_onboarding_core_v3'):
            module = importlib.import_module(name)
            require(Path(module.__file__).resolve() == (root / 'repo/ood' / (name + '.py')).resolve(),
                    'LEGACY_IMPORT_PATH:' + name)
        return sys.modules['constrained_onboarding_core_v3']
    finally:
        sys.path[:] = old


def load_legacy(root=None, with_training=False):
    root = Path(root or ROOT).resolve()
    core = get_core(root)
    phase = root / 'runs/phase_conditioned_calibration_v1_20261028/src'
    _file_module('_lg_historical_phase', phase / '__init__.py', package=True)
    data = importlib.import_module('_lg_historical_phase.data')
    dense = importlib.import_module('_lg_historical_phase.dense_source')
    target = importlib.import_module('_lg_historical_phase.target_evaluate')
    training = None
    if with_training:
        training = _file_module('_lg_frozen_training', root /
                               'runs/source_controls_base_ctx_v1_20261026/src/training.py')
    return dict(core=core, indexed=sys.modules['indexed_features_v1'], source_data=data,
                dense_source=dense, source_training=training, target_data=target)
