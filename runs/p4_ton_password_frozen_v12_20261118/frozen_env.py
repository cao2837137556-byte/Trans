"""Verify the sealed model, runtime and SLL field adapter before scientific work."""

import os
from pathlib import Path
import shutil
import sys

from common_ton import HERE, read, require, sha


def setup(project, *, local_runtime=None):
    freeze = read(HERE / "FROZEN.json")
    manifest = read(HERE / "PACKAGE_MANIFEST.json")
    for name, pin in manifest["files"].items():
        require(sha(HERE / name) == pin, "RUN_PACKAGE:" + name)
    older = local_runtime or project / freeze["runtime_package"]
    require(sha(older / "PACKAGE_MANIFEST.json") == freeze["runtime_manifest_sha256"], "PARENT_PACKAGE")
    for name, pin in read(older / "PACKAGE_MANIFEST.json")["files"].items():
        require(sha(older / name) == pin, "PRODUCTION_DEPENDENCY:" + name)
    sys.path.insert(1, str(older))
    sys.path.append(str(older / "repo/ood"))
    if local_runtime is None:
        import numpy as np
        from common_round1 import PYTHON, NUMPY_RUNTIME

        require(
            sys.platform.startswith("linux")
            and not sys.flags.optimize
            and os.environ.get("SLURM_JOB_ID", "").isdigit()
            and os.environ.get("SLURMD_NODENAME")
            and sys.version_info[:2] == (3, 11)
            and np.__version__ == "2.0.1"
            and Path(sys.executable).resolve() == PYTHON.resolve()
            and Path(np.__file__).resolve().is_relative_to((project / NUMPY_RUNTIME).resolve()),
            "FROZEN_SLURM_RUNTIME",
        )
    cfg = read(older / "CONFIG.json")
    geom = read(older / "GEOMETRY.json")
    require(
        cfg["method"] == freeze["method"]
        and cfg["method"]["p"] == 4
        and cfg["method"]["lambda_value"] == 0.25
        and all(geom["method"][k] == v for k, v in cfg["method"].items()),
        "ORIGINAL_V12_METHOD",
    )
    return older, freeze, cfg, geom


def store(project, freeze):
    from runtime_support import Store

    s = Store(project, ("reference", "runtime", "query", "raw_or_index"))
    s.specs.update(freeze["extra_pins"])
    return s


def decoder():
    from runtime_support import TSHARK_SHA

    p = Path(shutil.which("tshark") or "")
    require(p.is_file() and sha(p) == TSHARK_SHA, "FROZEN_DECODER")
    return p
