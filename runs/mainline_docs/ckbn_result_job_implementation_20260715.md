# CKBN result-job implementation

CKBN is the narrow missing diagnosis after CKBM: it distinguishes absent or
entangled frontend information from a backend ranking/calibration failure on
the already-used stream development canary. It does not introduce a new
detector or tune on stream/hydraulic.

The local real-data attempt certified the intended scope (8,671 legal fit rows,
385/385 support rows, 3,000 stream rows, 3,000 hydraulic rows, 27,196 future
attack rows across 16 families) but stopped before model fitting when pandas
could not hold the 10,042,291-row ip-camera prefix in workstation memory. Seven
of eight fit sources were materialized correctly. No scientific decision was
written from that incomplete run.

The full-source result job therefore uses the already validated
`scripts/00_env_issue27ckc.sh` environment and the CKBL/CKAT canonical frontend
on a 64 GiB node. The request is 8 CPUs, 64 GiB, and 8 hours; computation is
single-process source replay plus small HistGB probes, so additional CPUs or
GPUs would not be justified.

AMD and Intel submissions are independent. Their run roots, logs, source
caches, result archives, and SHA-256 files all include partition and job ID. If
both finish because the slower copy was not cancelled, neither can overwrite or
contaminate the other.

The job writes the actual scientific metrics and packages them automatically.
It is not an environment-only, preflight-only, audit-only, or synthetic-smoke
job. Large resumable source feature caches remain on HPC and are excluded from
the lightweight pullback archive.

