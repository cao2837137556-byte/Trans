# Vendored TabM provenance

- Project: `yandex-research/tabm`
- Upstream URL: <https://github.com/yandex-research/tabm>
- Release: `v0.0.3`
- Release commit: `a507095893d784c5702059d737ddfbd1299c41dd`
- License: Apache License 2.0; the upstream `LICENSE` is included unchanged.
- Upstream `tabm.py` SHA-256 after LF normalization:
  `fc654af6a16bac53d893a8265c79d7af4ebddcb95ad0d600cc6b6bc6b7317ade`
- Upstream `LICENSE` SHA-256 after LF normalization:
  `24330ebf083bc17c1db833b0109ef6ffc9019449330e9e4ec9797c061185c7a6`

`tabm.py` is the upstream release file. It is not a local approximation.
CKBM uses the basic numerical TabM path with `num_embeddings=None`.

Upstream declares `rtdl_num_embeddings` as a package dependency and imports
three embedding class names even on the no-embedding path. The frozen paper04
environment does not contain that package and installation is forbidden.
`rtdl_num_embeddings.py` in this directory is therefore a narrow compatibility
adapter: it exposes only those class names and raises on construction. It does
not implement or modify TabM.
