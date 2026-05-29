# Full Mirai Feature Compatibility Report

The compatibility gate does not pass for the current frozen LOW-GUARD++ instance.

Reason: the formal candidate is `original100 + HistGB-Conservative`, while the full Mirai assets are either dirty 116D or clean/restored 115D feature matrices. The repository's own historical documentation states that clean115 and original-frontend 100 are parallel input tracks and should not be mixed as the same result.

The full Mirai asset is therefore valuable, but the next experiment must choose one of two explicit routes:

1. Re-extract full Mirai into the current 100D frontend feature order, preserving row/timestamp provenance.
2. Define a new bounded `LOW-GUARD++-restored115` instance, recover feature mapping, and validate it as a separate representation-control path.

Micro-smoke was blocked because either route changes the representation relative to the frozen `original100` claim.
