# AI Conversation Brief: Transformer vs dA on Stronger-OOD Anomaly Detection

Date: 2026-04-08
Project: anomaly detection experiment track
Current mainline: original-frontend 100D + stronger OOD

## 1. What This Project Is Trying To Do

We are trying to make a Transformer-family anomaly detector outperform a dA / autoencoder baseline under a stronger open-world OOD evaluation.

The current formal comparison uses:
- ID benign traffic for normal calibration / thresholding
- OOD benign traffic for false alarm measurement
- high-purity attack traffic for attack detection measurement

The main target is not just high detection. The target is:

> high attack detection + controlled OOD benign alarm under fixed threshold and related operating points.

The user wants to continue searching for a Transformer win over dA. Do not suggest simply accepting dA as the final answer. It is okay to report that a Transformer experiment failed, but frame future reasoning around how to improve Transformer.

## 2. Evaluation Terms

Important metrics:
- `OOD benign alarm ratio`: false alarm rate on benign OOD traffic
- `high-purity attack detection`: detection rate on cleaner attack segments
- `fixed threshold`: formal threshold, usually ID-benign q99 / equivalent fixed protocol
- `naive calibration`: budget=5000, target=1%; repeatedly found to collapse attack detection
- `det50 constrained rule`: chooses a threshold with at least 50% attack detection while minimizing benign alarm

Important rule:
- All thresholds, centers, scalers, z-score stats, covariance fits, etc. must be based only on ID benign training/calibration data.
- Do not use OOD benign or attack data to fit scoring transforms.

## 3. Why This Became Hard

The dA baseline is surprisingly strong on the current stronger-OOD setting.
Typical dA fixed result used as reference:
- OOD alarm about `0.1209`
- high-purity attack detection about `0.7896`

The original Transformer and several variants tend to show one of two failure patterns:

1. High alarm and moderate/high detection.
2. Low alarm but detection collapses.

The central problem is therefore a representation/scoring trade-off problem, not just a threshold issue.

## 4. What Has Already Been Tried

### Threshold / calibration experiments

We tested fixed threshold, naive calibration, and detection-constrained threshold rules.

Finding:
- Naive calibration often reduces alarm but collapses detection to near zero.
- Detection-constrained thresholding is necessary, but cannot fully compensate for weak model separation.

Interpretation:
- The threshold rule matters, but it is not the whole solution.
- The Transformer representation / score distribution still needs improvement.

### MAE / MAE+TailReg / uncertainty variants

These variants generally lower OOD alarm, but also damage attack detection.

Examples:
- MAE+TailReg mask=0.4 fixed: alarm about `0.0709`, detection about `0.3208`.
- MAE+Latent mask=0.4 fixed: alarm about `0.1201`, detection about `0.5174`.
- dA fixed around the same stage: alarm about `0.1209`, detection about `0.7896`.

Interpretation:
- These input bottleneck / uncertainty / conservative-score mechanisms mostly suppress scores globally.
- They do not create enough attack separation.
- They are not the main path right now.

### Latent contrastive line

This became the most promising Transformer direction.

Core idea:
- Train Transformer with synthetic hard negatives in latent space.
- Best negative recipe so far: `latent_swap_spike_mix`.
- This raises attack detection substantially, but also raises OOD benign alarm.

Important single-seed result:
- `latent_swap_spike_mix` with improved scorer `log_weighted_z_rmse0.5_cos1.0`:
  - fixed alarm `0.1857`
  - fixed detection `0.8233`

This beat dA detection but had higher alarm than dA.

However, multi-seed verification weakened this result:
- new log-weighted score fixed mean: alarm `0.2161 +/- 0.0549`, detection `0.6353 +/- 0.1175`
- old scorer fixed mean: alarm `0.2220 +/- 0.0701`, detection `0.6558 +/- 0.0909`

Interpretation:
- The latent contrastive line has real signal.
- But the apparent single-seed score/postprocessing improvement was not stable enough.

## 5. Scorer Benchmark Result

We ran an offline latent scorer benchmark to test whether the latent representation was good but the scorer was wrong.

Key finding:
- Double-center / prototype direction scorer failed badly.
  - Example fixed: alarm `0.2734`, detection `0.0963`
- Mahalanobis / covariance-aware scorer had strong ranking signal but bad fixed alarm.
  - fixed Mahalanobis: alarm about `0.5843`, detection about `0.9476`
  - AUC about `0.8991`
  - det50 was healthy: alarm about `0.0516`, detection about `0.5015`

Interpretation:
- The promising signal is covariance-aware geometry, not prototype direction scoring.
- The Transformer latent space contains useful information, but fixed-threshold scoring is unstable.

## 6. Covariance-Regularized Experiments

### covreg_v1

Idea:
- Add a two-sided variance hinge and off-diagonal decorrelation to benign latent features.
- Try to make latent covariance healthier.

Best v1 fixed under old-best scorer:
- alarm `0.3550`
- detection `0.8874`

Comparison:
- no-compact latent old-best: alarm `0.1857`, detection `0.8233`
- dA fixed: alarm `0.1209`, detection `0.7896`

Interpretation:
- v1 raised detection, but alarm got too high.
- It did not solve the fixed-threshold trade-off.

### Mahalanobis epsilon-floor rescue

This was an offline rescoring experiment, no retraining.

Purpose:
- Test whether fixed Mahalanobis alarm exploded because a few low-variance / ill-conditioned covariance directions were over-amplified.

Key result:
- covreg_v1 original Mahalanobis fixed: alarm `0.6649`, detection `0.9536`
- covreg_v1 + full covariance diagonal loading f0.2: alarm `0.2246`, detection `0.8919`
- simple per-dimension variance floor failed: alarm low but detection collapsed

Interpretation:
- Full covariance diagonal loading is useful.
- Simple diagonal floor is not enough.
- The issue is not only tiny per-dimension variance; full covariance structure matters.

### covreg_v2

Idea:
- Train the covariance-aware diagonal-loading idea directly.
- Use EMA benign covariance buffer.
- Use Cholesky solve, no matrix inverse.
- Add benign tail penalty and synthetic negative push-out.
- Add weak anti-collapse floor.

Numerical stability:
- Cholesky failures: `0`
- NaN/Inf events: `0`

But the trade-off failed:
- best v2 fixed row: alarm `0.5003`, detection `0.8569`
- v1 rescue reference: alarm `0.2246`, detection `0.8919`
- no-compact old-best: alarm `0.1857`, detection `0.8233`
- dA fixed: alarm `0.1209`, detection `0.7896`

Diagnostics:
- v2 collapse dims: `48-64`
- v1 collapse dims: about `9-13`

Interpretation:
- The numerical linear algebra was stable.
- The failure was not Cholesky / matrix instability.
- The problem is likely training-objective alignment: the latent main loss and covariance score proxy are not aligned.
- The weak floor did not prevent latent dimensional collapse.
- The negative push-out / tau_ref may be too aggressive and may distort geometry.

## 7. Current Best Anchors

Keep these numbers in mind:

- dA fixed: alarm `0.1209`, detection `0.7896`
- no-compact latent + old-best score: alarm `0.1857`, detection `0.8233`
- covreg_v1 + offline diagload f0.2: alarm `0.2246`, detection `0.8919`
- covreg_v2 best: alarm `0.5003`, detection `0.8569`

Current state:
- Transformer can exceed dA detection.
- Transformer still struggles to match dA alarm at fixed threshold.
- The best clue is covariance-aware latent geometry, but training it directly in v2 made collapse worse.

## 8. What The Next AI Should Help Think About

The next AI should not restart from broad model search. It should reason from the evidence above.

Most useful next thinking directions:

1. How to align latent main loss with covariance-aware scorer without distorting geometry.
2. How to prevent latent dimension collapse before activating covariance score proxy.
3. Whether a staged schedule is needed:
   - stage A: train latent contrastive normally
   - stage B: freeze or partially stabilize latent geometry
   - stage C: introduce covariance tail control gently
4. How to make `tau_ref` less aggressive or more robust.
5. Whether negative push-out should be softened, delayed, or replaced by a ranking loss between benign and synthetic negative scores.
6. How to preserve the good offline behavior of `covreg_v1 + diagload_f0p2` while reducing alarm toward dA.

Avoid broad suggestions like:
- just add MAE again
- just use uncertainty
- just do prototype direction scorer
- just accept dA

These have already been tested or are not aligned with the current evidence.

## 9. One-Sentence Current Hypothesis

The Transformer latent space has attack-separation signal, and covariance-aware scoring exposes it, but the current training objectives either leave fixed alarm too high or distort the latent geometry; the next breakthrough likely requires a staged, anti-collapse covariance-aware training objective that preserves latent contrastive detection while controlling benign OOD tails.
