"""Superseded CKBH-v1 entrypoint.

The implementation at commit 195b1c26 is retained by Git for provenance, but
must not be rerun: its report-extension boolean check, cache cohort, and
negative sampler are invalid.  Use issue27ckbj_tgn_m1_strict_formal_v2.py.
"""

raise SystemExit(
    "CKBH-v1 is superseded and intentionally disabled; "
    "use repo/ood/issue27ckbj_tgn_m1_strict_formal_v2.py"
)
