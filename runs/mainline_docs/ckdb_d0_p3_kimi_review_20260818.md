# CKDB D0-P3 Kimi review — PASS with one required clarification (R1)

Date: 2026-08-18
Reviewer: Kimi
Target: `ckdb_d0_p3_combined_large_download_and_census_draft_20260818.md`
(Codex commits `5cd312b`, `559bfc7`)

## Verdict: PASS — seven questions ruled below; R1 must be written into the FROZEN text

## Independent verification performed

**U3 holdout selection recomputed from scratch.** I pulled the 27 UNSW
`source_unit_id`s from the D0-P1 device inventory, recomputed
`SHA256(UTF8(salt + NUL + candidate_id + NUL + source_unit_id))` for each,
sorted by `(key, source_unit_id)`, and took the first five. My result matches
the draft's §5.1 table **device-for-device and hash-for-hash**
(AmazonEcho `0093f325…`, WithingsSmartScale `04abb6f5…`, PixStarPhotoFrame
`066720e1…`, HelloBarbie `10d39088…`, TribySpeaker `186b4f4f…`). The
selection is genuinely deterministic and pre-body. PASS.

The draft also correctly incorporates: the D0-P2 Q3 boundary-verification
contract (§7 five-way classification, isolation + NO-GO, no replacement);
the CIC benign-only-before-transfer rule (§8); U2's corpus-global
descriptors (§10); U4's fine-groups-cannot-inflate rule; U6's secret
hygiene (mode-0600 runtime file, no credentials in Git/logs/screenshots)
and storage formula (§11); and the holdout role exclusions (§4).

## Rulings on the seven questions

**Q1 — P0-A/P0-B closure: a separately hashed, metadata-only launch
appendix is ACCEPTED.** Rationale: the authenticated identities depend on
the user's login session and cannot be known at freeze time, but they are
stable identities (publisher-relative paths, bytes, publisher checksums),
not protocol logic. Conditions: (a) the appendix closes P0-A–P0-C using
portal-exposed metadata only — filenames, sizes, checksums as listed by the
official authenticated inventory — never by opening object bodies; (b) the
appendix contains no transient URLs, cookies, tokens, or form state; (c)
the appendix gets its own SHA-256 sidecar and my expedited review before
launch authorization; (d) if any P0 cell cannot be closed from metadata,
the draft returns to review as §2 already states.

**Q2 — quality-support thresholds without a U2 route-kill gate: ACCEPT.**
This discharges the decision I reserved at the U-convergence. A numerical
coverage kill would conflate three questions already governed elsewhere —
boundary validity (§7/§8), independent-domain count (the ≥3 gate), and the
I1 scale gate (§9) — and a coverage gap does not invalidate a corpus, it
bounds what the corpus can teach. The draft's mechanism (six regions,
100-session/10k-packet/2-unit quality support, `COVERAGE_GAP_NAMED` caps
claims and activates the U1 horizon audit) is the scientifically honest
one, and it matches my original U2 wording ("a named gap does not stop
training; it caps the claim").

**Q3 — five-device consumer holdout: ACCEPT, with a reporting caveat.**
5/27 preserves 22 fit devices and gives a real unseen-benign probe. But a
5-domain probe yields wide intervals, not tight bounds: holdout metrics
must be reported per-device with the small-n caveat, may only cap or
support claims descriptively, and can never substitute for FINAL. If FROZEN
restates this caveat in §5.1, nothing further is needed.

**Q4 — industrial option 2 mechanically forced: ACCEPT.** The arithmetic is
correct: coarse-domain maximum is CIC 1 + PNNL 2 = 3, and holding one out
would leave two fit domains, below the inherited route minimum; therefore
`USE_ALL_THREE_INDUSTRIAL_DOMAINS_FOR_FIT_SELECT` is the only consistent
choice. Its price must travel into the paper claim contract verbatim:
**no broad unseen-industrial-domain generalization claim before FINAL**;
the industrial generalization claim rests on cooler-motor alone.

**Q5 — PNNL boundary test without reading bodies: ACCEPT as the strongest
body-free test available.** Publisher-scenario-name mapping with unique
nonempty normal units per sector, disjointness from attack/fault/ambiguous
after path normalization, and allowlist freeze before any decode is the
maximum rigor compatible with the pre-open principle. Residual risk (a
publisher "normal" member containing mislabeled traffic) cannot be excluded
without payload access and is honestly bounded: the two normal allowlists
should carry the boundary class
`BENIGN_ONLY_MEMBER_BY_PUBLISHER_SCENARIO` in the census outputs, and the
U2 census then provides distributional evidence after the fact. No change
required beyond naming that class.

**Q6 — CIC stays launch-blocked without a benign-only remote member set:
ACCEPT — and this generates required clarification R1.** A mixed whole
archive filtered after packet access is exactly the contamination path this
protocol family exists to prevent; the block must stand even if it costs
the route. R1 (must be explicit in FROZEN): the route-level consequence is
currently implied but not stated — (a) if P0-B cannot be closed from the
authenticated inventory, the draft returns to review with CIC contributing
zero domains (§2 already covers this); (b) if the post-transfer §8 checks
fail, `CIC_BENIGN_BOUNDARY_FAILURE_NO_USE` fires; (c) **in either case the
industrial maximum is 2 < 3, D0-P3 terminates with a named scientific
result, and no third corpus may be searched** — the second-corpus remedy
was spent on PNNL and the no-replacement rule covers this branch too.
Stating (c) verbatim in FROZEN closes the last discretion hole.

**Q7 — storage formula: ACCEPT as adequately conservative; practical
warning attached.** The dual-branch formula with 1.20 margin and the inode
gate are sound, and making P0-D a launch-time measurement (not freeze-time)
is correct because free space is volatile. But the user should know now:
at 40.48 GiB free on D:, the launch gate will almost certainly **block** —
even UNSW alone plausibly needs on the order of 60+ GiB under
`1.20 × max(2C, C+E+D)` once extraction and the 20 GiB derived-data floor
are counted. Fail-closed blocking is the correct behavior; the practical
action is to free substantially more D: space (or designate a larger
volume) before launch authorization, otherwise the protocol will do its job
and refuse to start.

## What this review authorizes

- Codex may produce the FROZEN D0-P3 protocol with R1 written in, generate
  the SHA-256 sidecar, and present both for freeze verification. After
  freeze verification: implementation + 30 contract tests → my
  implementation review → P0 launch appendix (Q1 mechanics) → my expedited
  appendix review → fresh P0-D measurement → explicit user authorization →
  transfer.

This review does **not** authorize: implementation, any HTTP request,
account use, object-body download, archive opening, HPC, training, or
FINAL contact.
