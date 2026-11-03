"""Explicit frozen test-code location; never load model/data as a fallback."""
import hashlib
import os
from pathlib import Path


def frozen_test_root():
    here = Path(__file__).resolve().parent
    explicit = os.environ.get('PAPER04_FROZEN_R2_TEST_ROOT')
    if explicit:
        root = Path(explicit).resolve()
    else:
        extracted = here.parent/'dense_reference_matrix_v1_20261027/distribution/r2/validation/extracted/dense_reference_matrix_v1_20261027'
        root = extracted if extracted.is_dir() else here.parent/'dense_reference_matrix_v1_20261027'
    seal = root/'PACKAGE_SHA256SUMS'
    encoder = root/'vendor/encoding_v2/repo/ood/onboarding_supplement_encoder_r2.py'
    if hashlib.sha256(seal.read_bytes()).hexdigest()!='ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120':
        raise RuntimeError('INERT_TEST_FROZEN_R2_IDENTITY')
    if hashlib.sha256(encoder.read_bytes()).hexdigest()!='c9648f0468431b55a5fc0a3532b00c42447372c4ad6eec64ccfdf1ee353dc959':
        raise RuntimeError('INERT_TEST_FROZEN_ENCODER_IDENTITY')
    return root
