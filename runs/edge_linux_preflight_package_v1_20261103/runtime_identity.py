"""Record actual installed numerical runtime, without an encoder or evaluation."""
import argparse
from contextlib import redirect_stdout
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def capture(tshark):
    import numpy as np
    import torch
    numpy_details = io.StringIO()
    with redirect_stdout(numpy_details):
        np.show_config()
    cpu = {}
    if Path('/proc/cpuinfo').is_file():
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if ':' in line:
                key, value = map(str.strip, line.split(':', 1))
                if key in ('model name', 'vendor_id', 'cpu family', 'model', 'stepping'):
                    cpu.setdefault(key, value)
    versions = {}
    for name in ('numpy', 'torch', 'transformers', 'safetensors', 'psutil', 'dpkt', 'pandas'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return dict(scope='RUNTIME_IDENTITY_ONLY_NO_MODEL', system=platform.system(),
        platform=platform.platform(), python=platform.python_version(), executable=sys.executable,
        cpu=cpu, versions=versions, numpy_blas_configuration=numpy_details.getvalue(),
        torch_build_configuration=torch.__config__.show(),
        mkldnn_available=torch.backends.mkldnn.is_available(), mkldnn_enabled=torch.backends.mkldnn.enabled,
        torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        tshark_version=subprocess.run([tshark, '--version'], text=True, capture_output=True,
                                     check=True, timeout=15).stdout,
        runtime_or_precision_changed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tshark', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = Path(args.output)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(capture(args.tshark), stream, indent=2)
        stream.write('\n')
