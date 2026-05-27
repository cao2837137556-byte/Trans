# Reviewer Defense: LOW-GUARD++ Candidate Freeze

## Q1: Why did you not run the full formal validation?

Because the issue27d candidate was not a single frozen configuration. Two HistGB-Conservative configs were selected across the smoke bins/seeds. A formal run after choosing one post hoc would risk hindsight model selection.

## Q2: Is the LOW-GUARD++ candidate invalid?

No. It remains promising. The blocker is protocol hygiene: the candidate must be frozen before final-eval reporting.

## Q3: Did issue27e use final eval to choose a config?

No. issue27e stopped before the formal run.

## Q4: What is the correct next experiment?

Freeze a candidate config using only support-validation / OOD-validation evidence and pre-registered simplicity rules, then run full locked seeds.

## Q5: Can the paper claim LOW-GUARD++ now?

No. The allowed claim is that a strong original100 HistGB candidate was found in smoke and needs formal validation.
