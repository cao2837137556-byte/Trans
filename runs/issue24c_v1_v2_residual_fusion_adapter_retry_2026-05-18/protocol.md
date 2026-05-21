# Protocol

This run only tests V1/V2 score fusion after issue24b diagnosed complementarity. V1 is original100+kcenter32+fixed guard LR. V2 is selected_source_rich_top64+kcenter32+fixed guard LR. Fusion candidates are linear alpha score fusion, residual LR over fixed score features, and conservative max fusion. Fusion configuration selection uses support-train/support-holdout plus ID calibration and OOD validation only. Final OOD eval and attack eval are report-only.
