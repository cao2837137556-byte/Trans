# Source Provenance

- Upstream project: `ymirsky/Kitsune-py`
- Upstream repository: `https://github.com/ymirsky/Kitsune-py`
- Imported commit: `28a654b5813936380d264c0934136efda672174a`
- Imported date: `2026-03-22`

## Imported original files
- `FeatureExtractor.py`
- `netStat.py`
- `AfterImage.py`
- `LICENSE.original`

## Local compatibility adjustments (minimal)
- `netStat.py`: `pyximport` import made optional so pure-Python `AfterImage.py` can run when `pyximport` is unavailable.
- `FeatureExtractor.py`:
  - added missing `import sys` for TSV path;
  - made Scapy import optional and fail-fast with clear message when pcap parsing via Scapy is requested but unavailable.
- `AfterImage.py`: replaced `np.Inf` with `np.inf` for NumPy 2.x compatibility.

No feature-engineering logic was rewritten.
