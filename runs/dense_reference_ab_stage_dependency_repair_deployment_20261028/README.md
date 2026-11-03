# Fixed repair transfer and metadata-only engineering preflight

This layer is separate from the sealed scientific repair package. It uploads
only the exact archive bound by local `prepare`, at most 2 MiB, through the
existing authenticated `school-hpc` SOCKS connection. It never creates SSH
sessions and contains no scheduler submission or arbitrary remote execution API.

The remote bridge is loopback-only port 18788, expires after one hour, and
requires a private random token. The fixed endpoints are:

- `GET /status` and `GET /result`.
- `PUT /archive`: one full archive, exact length and SHA, exclusive create.
- `POST /deploy`: exact fixed top-level archive prefix, exact manifest member
  set and file hashes, no links/traversal, exclusive new repair directory.
- `POST /preflight`: one engineering attempt, original environment SHA, exact
  original NumPy 2.0.1 overlay, one thread; synthetic tests followed by the fixed
  real metadata/q14/UID/source-seal/input-SHA gate. Outputs stay outside the seal.

The real-input metadata gate does not compute E3, distances, supports, target
score evaluations, model forwards, encoding, training or CAL. The preceding
synthetic tests exercise scientific helper paths only on synthetic inputs;
zero counters in the transport receipt explicitly refer to real target data.
Neither phase calls the repaired
scientific launcher or its Slurm file. A successful gate does not authorize or
submit the next scientific job. The consumed 179680 authorization is untouched.

From the project root, after the repair archive is sealed and independently
reviewed, run with the project's existing Python 3.10:

```text
python -B runs/dense_reference_ab_stage_dependency_repair_deployment_20261028/preflight_client.py prepare --archive <exact sealed archive> --package-sha <PACKAGE_SHA256SUMS SHA256>
```

The command prints only non-secret identity. `.private/bootstrap.command.sh`
must be read directly into the computer-use runtime and typed into the already
authenticated VS Code remote Linux terminal; never print its contents or token.
The bootstrap only starts the bounded engineering bridge. After its marker,
run these client actions individually and inspect each result:

```text
python -B runs/dense_reference_ab_stage_dependency_repair_deployment_20261028/preflight_client.py inspect
python -B runs/dense_reference_ab_stage_dependency_repair_deployment_20261028/preflight_client.py upload
python -B runs/dense_reference_ab_stage_dependency_repair_deployment_20261028/preflight_client.py deploy
python -B runs/dense_reference_ab_stage_dependency_repair_deployment_20261028/preflight_client.py preflight
```

The last action can take up to eight minutes but should normally take seconds;
run it with a yielding tool call so the user can still receive updates. If the
client connection is interrupted, `result` reads the fixed saved gate receipt;
do not invoke `preflight` again. All writes are independent of the original
candidate, r1 distribution and 179680 runtime. Keep failures for review.

Local transport tests cover archive identity, bad manifest identity, traversal,
links, unregistered members, scope and byte budgets, exclusive extraction and
refusal to overwrite an existing repair. Tests use temporary synthetic files.
