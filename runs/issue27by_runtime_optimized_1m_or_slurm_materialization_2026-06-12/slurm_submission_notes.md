# Slurm Submission Notes

This is a data materialization pipeline, not a model experiment.

1. Copy the worktree and Gotham dataset paths to the compute environment.
2. Build the ID train frontend state once:
   `python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode build-train-state`
3. Submit the array job from the worktree root:
   `sbatch runs/issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12/slurm_job_plan.sh`
4. Do not merge until every required cache is valid and no quarantine item is required.
5. Sealed final roles remain report-only; this pipeline does not train models.
