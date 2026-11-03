"""Import-only gate for the isolated HPC numerical environment; no model init."""
import argparse
import importlib
import importlib.metadata
import io
import platform
import contextlib
from pathlib import Path
import sys

from common import read, require, write


def probe(overlay, versions):
    overlay = Path(overlay).resolve()
    import numpy as np
    require(np.__version__ == '2.0.1' and Path(np.__file__).resolve().is_relative_to(overlay),
            'NUMPY_OVERLAY_NOT_IMPORTED')
    modules = {'torch': 'torch', 'numpy': 'numpy', 'transformers': 'transformers',
               'tokenizers': 'tokenizers', 'safetensors': 'safetensors',
               'huggingface_hub': 'huggingface_hub'}
    info = {}
    for name, version in versions.items():
        distribution = importlib.metadata.distribution(name.replace('_', '-'))
        module = importlib.import_module(modules[name])
        actual = getattr(module, '__version__', distribution.version).split('+')[0]
        require(distribution.version.split('+')[0] == version and actual == version,
                'RUNTIME_VERSION:' + name)
        if name == 'numpy':
            require(Path(distribution.locate_file('')).resolve().is_relative_to(overlay),
                    'NUMPY_DISTRIBUTION_SHADOWED')
        info[name] = dict(version=actual, path=module.__file__)
    import torch
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    require(torch.from_numpy(np.ones(2, dtype=np.float32)).numpy().tobytes() ==
            np.ones(2, dtype=np.float32).tobytes(), 'NUMPY_TORCH_BRIDGE')
    # Import precisely the wrapper used by the sealed encoder. This performs
    # no e3_runtime call, checkpoint load, tokenization or neural forward.
    for module in ('pandas', 'psutil', 'legacy_unsw_archival_runtime_v1',
                   'constrained_onboarding_reference_v2', 'continuous_features_v3',
                   'issue27ckda_d1_e3_embed_v1', 'issue27ckda_d0_resource_pilot_v1'):
        loaded = importlib.import_module(module)
        info[module] = dict(path=loaded.__file__)
    translator = importlib.import_module('issue27ckda_d0_resource_pilot_v1')
    source = Path(__file__).resolve().parents[1] / 'vendor/encoding_v2/runtime/vendor/netFound'
    classes = translator.import_netfound(source)
    info['netFound_classes'] = [dict(name=cls.__name__, module=cls.__module__)
                                for cls in classes]
    blas = io.StringIO()
    with contextlib.redirect_stdout(blas):
        np.show_config()
    return dict(status='PASS', python=sys.version, platform=platform.platform(),
                dependencies=info, neural_forwards=0, checkpoint_loads=0,
                torch_cpu_capability=torch.backends.cpu.get_cpu_capability(),
                torch_config=torch.__config__.show(), numpy_config=blas.getvalue(),
                original104_parity='NOT_ASSESSED', hardware_identical_claim=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--overlay', required=True)
    parser.add_argument('--versions', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    write(args.output, probe(args.overlay, read(args.versions)['production_runtime_versions']))
