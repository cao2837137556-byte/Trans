# Post-N3 focused literature review

Date consulted: 2026-09-08. Purpose: design a credible next test of the preserved
N3 candidate and distinguish inherited decisions from benefits of B training.
This is a targeted review, not an exhaustive systematic literature survey.

## Retrieval and evidence scope

Public retrieval used arXiv's Atom API (title/topic searches followed by exact
version lookup) and public HTML. Search topics covered network intrusion
candidate comparison, backward compatibility/negative flips, security evaluation
leakage/dependence, and netFound. Version metadata for all five retained entries
was checked through id_list=2609.04388v1,2608.15761v1,2402.01359v2,
2301.10546v1,2310.17025v5. The URLs below are reproducible primary sources;
this note does not purport to be a verbatim search-request log.

General web search did not yield usable results in this environment. The scope
is therefore the directly retrieved primary papers, not a claim to have found
every recent method. No dataset, checkpoint or benchmark repository was fetched.
The descriptions below paraphrase selected text; no local project conclusion
is inferred from a paper's benchmark accuracy.

## 1. Candidate comparison in NIDS

Candidate Comparability Before Promotion: Conditional Validation in Adaptive
Network Intrusion Detection. arXiv:2609.04388v1, posted 2026-09-03, PREPRINT.

- Record: https://arxiv.org/abs/2609.04388v1
- Text: https://arxiv.org/html/2609.04388v1
- Read: abstract/introduction and selected experimental/control sections on
  preprocessing ownership, evidence size and feature-disjoint comparisons.
- Relevant finding: a nominal old/new comparison can mix the value of a new
  candidate with differences in preprocessing ownership and training evidence.
  Successful construction and justified replacement are separate questions.
- Applied here: freeze the complete N3 pipeline; compare identical target UIDs;
  record all learned-component exposure; keep finite fit repair separate from
  retained behavior on the next pool.
- Not adopted: their drift/promotion machinery, balanced-accuracy tradeoffs or
  sequential confidence gates. Our source-dependent development pool does not
  establish their risk assumptions, and B utility cannot offset A failures.

## 2. NIDS provenance shortcuts

Provenance, Not Behaviour: A Serialisation Artifact in Edge-IIoTset and a
Leakage-Free Benchmark for Precision-Agriculture Intrusion Detection.
arXiv:2608.15761v1, posted 2026-08-16, PREPRINT.

- Record: https://arxiv.org/abs/2608.15761v1
- Text: https://arxiv.org/html/2608.15761v1
- Read: abstract/introduction and serialization-artifact description.
- Relevant finding: class-correlated source serialization, including different
  spellings of absent numeric fields, can support impressive apparent accuracy
  without demonstrating behavior recognition.
- Applied here: retain source/member/behavior provenance, distinguish literal
  labels from behavior correspondence, and qualify representation dependencies.
  A single attack source cannot become 2,000 independent behavior trials.
- Not inferred: no evidence from this paper shows that F4 has that artifact.
  It does not justify repeating the passed field audit, changing F4 fields or
  downloading its proposed benchmark.

## 3. Security evaluation dependence

TESSERACT: Eliminating Experimental Bias in Malware Classification across
Space and Time (Extended Version). arXiv:2402.01359v2, initially posted
2024-02-02, updated 2025-04-09; extended version of earlier TESSERACT work.

- Record: https://arxiv.org/abs/2402.01359v2
- Text: https://arxiv.org/html/2402.01359v2
- Read: abstract/introduction and evaluation-bias framing.
- Relevant principle: spatial/temporal evaluation choices and lookahead can
  inflate security-model conclusions relative to intended deployment.
- Applied here: label old F1 validation as exposed development; preserve its
  membership; list source/session/pretraining unknowns; avoid row-level iid
  confidence claims or declaring a new split untouched.
- Limit: malware results are methodological precedent, not direct proof about
  this traffic corpus or a ready-made new-device protocol.

## 4. Retaining old-correct decisions

Backward Compatibility During Data Updates by Weight Interpolation.
arXiv:2301.10546v1, posted 2023-01-25.

- Record: https://arxiv.org/abs/2301.10546v1
- Text: https://arxiv.org/html/2301.10546v1
- Read: problem formulation, interpolation approach and relevant limitations.
- Relevant metric: negative flip rate counts old-correct/new-wrong cases over
  all evaluated cases. Conditional regression among old-correct cases has a
  different denominator. Aggregate accuracy alone can conceal regressions.
- Applied here: paired per-UID transitions with separate attack/benign
  protection; A NFR denominator 3,176 versus conditional denominator 3,174.
- Not adopted: weight interpolation between old netFound and the new GRU.
  Their parameters do not share compatible coordinates/architecture, and the
  paper's compatible-ancestry setting is not established here. No alpha search,
  extra candidate or N3 weight change follows from this citation.

## 5. The old pretrained representation

netFound: Principled Design for Network Foundation Models.
arXiv:2310.17025v5, initially posted 2023-10-25, updated 2026-05-12.

- Record: https://arxiv.org/abs/2310.17025v5
- Text: https://arxiv.org/html/2310.17025v5
- Read: abstract/introduction and selected frozen-encoder comparison discussion.
- Relevant design: protocol-aware tokenization, context and burst/flow hierarchy
  combine with pretraining; downstream head fitting is a distinct contribution.
- Applied here: broader input coverage is not itself inherited pretrained
  knowledge. State old/new preprocessing, representation and head identities
  separately and document uncertain pretraining overlap.
- Limit: this paper revision does not identify our pinned old E3 checkpoint or
  establish its exact pretraining corpus. No new model or checkpoint is selected.

## Project-specific decision

Reuse N3 first, then compare the whole available 4,400-target development pool.
Use paired protection and descriptive B utility. This is a targeted application
of comparison and evaluation principles, not a claim that the literature proves
the candidate will pass or that the proposed test is itself a novel algorithm.

For causal B-training value, require a separately matched pair from a common
pre-B initialization and account for all B exposure, including prefixes and
auxiliary learning. This requirement follows from the project training lineage
and the intended causal comparison; none of the cited papers validates our
particular GRU/head repair or supplies a performance guarantee.

The latest papers strengthen the need for comparable evidence and provenance.
They do not currently provide grounds to discard the repaired candidate, relax
frozen gates, change the frontend, or begin downstream new-device experiments.
