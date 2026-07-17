# MiniRocket multivariate provenance

- Method: MiniRocketMultivariate.
- Upstream project: `sktime/sktime`.
- Upstream release: `v0.24.1`.
- Upstream implementation:
  `sktime/transformations/panel/rocket/_minirocket_multi_numba.py`.
- License: BSD-3-Clause; the exact upstream license is copied in `LICENSE`.
- Paper: Angus Dempster, Daniel F. Schmidt, Geoffrey I. Webb,
  *MINIROCKET: A Very Fast (Almost) Deterministic Transform for Time Series
  Classification*, KDD 2021.

`minirocket_torch.py` is a project-local execution-port of the upstream
MiniRocketMultivariate parameterization: the 84 fixed length-nine kernels,
log-spaced dilations, log-uniform channel subsets, golden-ratio quantiles,
random training-instance bias fitting, alternating padding, and PPV pooling are
retained.  The Numba kernels are replaced by batched `torch.conv1d` because the
frozen Python 3.9 HPC environment contains PyTorch but does not certify Numba
or sktime, and the project forbids installing dependencies.  The port does not
change the method or learn convolution weights.
