# CKBI → CKBH seed-27 HPC bundle

This bundle is the entire two-stage chain.  It does not use remote Git or
perform an environment-only/preflight-only submission.

1. Verify `SHA256SUMS` after extraction.
2. Run `bash issue27ckbi_install_and_submit_chain.sh` from the extracted
   bundle root.
3. The helper copies only four payload files when the exact target is absent
   or byte-identical, then submits CKBI stage A and CKBH stage B with
   `afterok` dependency.
4. Read `ckbi_extension_job_id.txt` and `ckbh_formal_seed27_job_id.txt` for
   the two job IDs.  If CKBI fails, CKBH remains blocked and does not train.

Stage A produces the extension cache plus manifest/alignment/exclusion
artifacts.  Stage B runs seed 27 only and writes scientific metric tables and
the go/no-go JSON.  Seeds 37/47 are not submitted by this bundle.
