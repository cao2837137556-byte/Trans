# Evidence Map

## A-level evidence

- Fixed OOD guard mechanism: issue10/issue11 show lower OOD alarm and improved feasibility without major detection loss.
- original100 fixed guard as current stable GDA-minimal: issue11 gives main and held-out support seed evidence.
- Support and threshold provenance cleanliness: support IDs and threshold provenance pass in issue11/issue12.

## B-level evidence

- source_rich is useful but unstable: source_rich can improve or complement detection, but held-out seed evidence limits universal claims.
- Transformer hidden integration is feasible: issue12 recovers current-protocol hidden cache and shows original100+hidden fixed guard can remain feasible, but it does not clearly beat original100 fixed guard on held-out seeds.

## C-level / negative evidence

- Scalar score fusion is insufficient: dA and Transformer score-only adapters fail; original100+scalar score does not materially improve over original100-only.
- Hidden-only failure: Transformer hidden alone remains low-detection and high-OOD-alarm.
- Detector-agnostic adaptation is not yet proven.

## Missing evidence

- Arbitration matrix experiment.
- Harder holdout or second-environment validation.
- Upgraded adapter beyond LR.
- External validation.
