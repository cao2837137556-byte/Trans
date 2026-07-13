# CKBJ M1 v2 launcher correction after job 151220

## Observed failure

- Slurm job: `151220`
- State: `FAILED`
- Exit code: `127:0`
- Elapsed: `00:00:13`
- Environment output: `torch=2.5.1`, `torch_geometric=2.6.1`
- Exact error: `/usr/bin/time: No such file or directory`
- Scientific status: training never started; no metric or model conclusion.

## Minimal correction

1. Remove the undeclared `/usr/bin/time` executable dependency.
2. Record UTC start/end, wall seconds, and Python exit code with Bash built-ins
   and standard `date`.
3. Leave Python stderr attached to the Slurm error log so a future model error
   is visible to the status helper.
4. Export `sacct` accounting, including `MaxRSS`, during result packaging.
5. Submit with explicit `--chdir`, `--output`, and `--error` paths rooted in
   the remote project directory.
6. Let the status helper read both the corrected project-root log path and the
   legacy bundle-relative path used by job `151220`.
7. Permit replacement of the remote Slurm file only when its SHA-256 equals
   the exact superseded r2 launcher hash; refuse every other differing target.
8. The r3 installer stopped before `sbatch` because the existing r2 Python
   payload used CRLF while the corrected payload used LF.  A normalized diff
   proved both Python files content-identical.  The replacement installer
   accepts only CRLF-normalized equality for existing text targets; it still
   refuses any substantive Python difference.

## Preserved boundaries

No dataset, cache, role split, manifest, feature, negative sampler, model,
threshold, seed, or scientific decision rule changed.  CKBI job `150547` and
its report-only cache remain read-only and are not resubmitted.  The corrected
submission is Stage B only and still runs exactly seed `27`.
