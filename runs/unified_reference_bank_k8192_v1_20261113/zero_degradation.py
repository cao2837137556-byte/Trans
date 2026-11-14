"""Paired zero-degradation gate. Weights are the identical frozen evaluation values."""
from fractions import Fraction

import numpy as np


def paired_cell(old, new, weight, *, attack):
    old=np.asarray(old); new=np.asarray(new); weight=np.asarray(weight)
    if not (old.dtype==new.dtype==np.bool_ and old.shape==new.shape==weight.shape and old.ndim==1
            and np.isfinite(weight).all() and (weight>0).all()):
        raise ValueError('FROZEN_EVALUATION_CELL')
    if len(old)==0:
        return dict(status='NOT_APPLICABLE',rows=0,n00=0,n01=0,n10=0,n11=0)
    add=new & ~old; drop=old & ~new; both=old & new
    n01=int(add.sum()); n10=int(drop.sum()); n11=int(both.sum())
    # Compare exact stored binary weights, so a positive change never rounds to a pass.
    def mass(flags):
        return sum((Fraction(float(x)) for x in weight[flags]), Fraction())
    delta=mass(add)-mass(drop)
    ok=n10==0 if attack else n01<=n10 and delta<=0
    return dict(status='PASS' if ok else 'FAIL',rows=len(old),n00=len(old)-n01-n10-n11,
                n01=n01,n10=n10,n11=n11,weighted_delta=float(delta),
                weighted_delta_numerator=delta.numerator,weighted_delta_denominator=delta.denominator)
