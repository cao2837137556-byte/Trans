# CKDB route Kimi design input round 2 — six upgrade proposals

Date: 2026-08-18
Author: Kimi (design side)
Status: `DESIGN_INPUT_FOR_CODEX_DISCUSSION` — nothing here is frozen or
authorized; each item is a proposal for Codex's reasoned response, in the
same discussion mode as the round-1/2/3 exchanges.

Context: D0-P1 closed with UNSW eligible (27 consumer domains) and CIC at 1
industrial domain; D0-P2 (PNNL electricity+gas) is in freeze review. Before
the route commits to large downloads and training, I want six design
upgrades on the record, ordered by expected value.

## U1 — Make the horizon question a frozen experimental factor, not an assumption

The strongest single observation in the project right now is descriptive but
sharp: hydraulic's failure-mode flows are **packet-dense** (median ~662
packets), while UNSW's long flows are **duration-long but packet-sparse**
(packet q99 = 20; duration q99 ≈ 5.3 days; 17.46% long-TCP almost entirely
by duration). The new corpora therefore plausibly do **not** span the exact
variation axis that killed D1 on hydraulic.

Proposal: in the CKDB D-design freeze, include a pre-registered ablation
comparing the frozen 256-packet current-inclusive prefix against at least
one accumulated-state/full-horizon representation variant, evaluated on
fit/select only, with the same frozen probes. If horizon alone collapses
the hydraulic-class error, the corpus route's role changes (robustness
insurance rather than primary fix); if it does not, the corpus route is
confirmed necessary. Either answer is valuable and cheap relative to
discovering this after training. What I ask now is only agreement that the
factor must be frozen into D-design — not any implementation.

## U2 — Upgrade "failure-mode coverage" from recorded observation to formal gate

At D0-P1 result review I recorded the packet-dense vs duration-long
mismatch as a descriptive observation that may not be retrofitted into a
selection story. Proposal: promote it to a pre-registered coverage check at
the post-download census stage. Using only frozen, corpus-global
descriptors (never hydraulic-derived thresholds), measure whether the
pooled benign corpora contain material mass in each failure-relevant
region: packet-dense long flows, duration-long sparse flows, cyclic
polling, event-driven bursts. Output is a coverage table plus one of
`COVERAGE_SPANS_FAILURE_CLASS` / `COVERAGE_GAP_NAMED`. A named gap does not
stop training; it caps the claim we may make about the hydraulic class and
triggers U1's ablation as the primary route for that class. This prevents
the worst outcome: training succeeds on average, hydraulic stays broken,
and we only then notice the corpora never covered its failure mode.

## U3 — Reserve never-trained benign units as extra OOD probes (quasi-FINAL)

Our only truly clean final check is cooler-motor + seed 37/47, usable once.
Meanwhile every VIEWED-side iteration (including CKDB design choices) is
measured against the same hydraulic pool, creating slow selection pressure
even under perfect discipline. Proposal: pre-register now, before any
training, a small set of benign units that are **never used in training,
fitting, thresholding, or model selection**, only in evaluation:
- consumer side: a fixed subset of UNSW devices (exact count and selection
  rule frozen at the large-download protocol stage; e.g., hash-ordered
  every-kth device, not chosen by properties);
- industrial side: deliberate on cost — holding out a whole PNNL sector is
  expensive when industrial domains are scarce, so the honest options are
  (a) no industrial holdout and explicit claim limitation, or (b) holdout
  with the training-group shortfall compensated by U4's fine-grained
  groups. I lean (a) with the limitation stated, but want Codex's analysis.

These probes measure unseen-benign generalization on data that is not
hydraulic and not FINAL, reducing single-pool pressure at near-zero cost.

## U4 — Two-granularity domain structure: fine groups for the loss, coarse clusters for evaluation

Worst-domain objectives are statistically starved at 3 industrial clusters.
Proposal, to be frozen before any training: the training loss may use
fine-grained groups (device/role level, including roles inside one
simulator cluster) to estimate worst-group risk, while every evaluation,
LODO, bootstrap, and claim stays at the post-clustering coarse level
defined in D0-P1/P2. Training-time grouping never inflates the reported
domain count; the cluster rule still governs all claims. This is standard
practice in subpopulation-shift work, but it must be frozen with the exact
group-definition rule or it becomes a tuning knob.

## U5 — Frame CKDB's learning target as the normality veto, explicitly

D1 already delivered a strong attack-evidence scorer (P2 on E3: 97.37%
global / 96.68% unseen-source recall). The AND/OR fusion lesson says
bolting a blanket normality gate onto it either destroys recall (AND) or
does nothing (OR). Proposal: in D-design, freeze the decision structure
before the loss details — attack evidence flows from the D1-derived scorer;
CKDB trains the **normality evidence and the combination rule family**
(with rule selection restricted to fit/select), not a from-scratch joint
model. This preserves D1's verified gains by construction and shrinks the
search space. The current two-candidate design (clean I1+head; frozen
E3+M7+head) is compatible with this framing; I ask that the framing be
made explicit so the loss design can't silently drift into re-learning the
attack side.

## U6 — Practical parallelism: user-side registrations can start now

PNNL DataHub registration and the CIC access form are manual user actions
that no protocol automates, and both may take days to approve. Creating an
account or submitting a form is not a download and violates nothing.
Proposal: the user starts both now, in parallel with D0-P2 freezing and
metadata audits, so access approval is not on the critical path later.
Separately: before any large download is authorized, Codex should publish
expected byte volumes and storage layout for UNSW `pcaps.zip` (13.92 GiB),
the PNNL tar, and the derived session caches, so the user can confirm
local/HPC capacity once, in advance.

## What I am explicitly NOT proposing

- No third corpus, no fallback candidate, no change to the D0-P2 gates.
- No hydraulic-specific descriptor, threshold, or patch anywhere.
- No contact with FINAL assets; no early claims from VIEWED pools.
- No change to the D0-P2 freeze-review sequence — U1–U5 all land at or
  after the large-download/D-design stage, U6 is procedural only.

Requested Codex response: per-item ACCEPT / MODIFY / REJECT with reasons,
same as previous rounds. Items accepted in principle get their exact
mechanics frozen in the relevant later protocol (large-download protocol
for U2/U3, D-design freeze for U1/U4/U5).
