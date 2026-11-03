"""Exact original C0/R updates, selected by distinct new arm identifiers."""
import issue27frontend_abstart_support_v1 as s
import issue27frontend_transfer_model_v1 as original
import issue27frontend_aligned_model_v1 as aligned
from issue27frontend_aligned_model_v1 import (
    Student, Projection, configure, state_hash, optimizer, huber,
    label_loss, guard_loss, gradient_norm, teacher_terms)


def update(model, projection, opt, a, b, arm, epoch, guard, cache, r, charge=lambda batch: None):
    if arm == 'C0_AB':
        s.require(projection is None, 'C0_PROJECTION_FORBIDDEN')
        # Neither cache nor guard is passed into the original C0 numerical path.
        stats = original.update(model, None, opt, a, b, 'C0', epoch, None, None, r, charge)
        stats.pop('teacher')
        stats.update(task_score=0., residual=0., teacher_targets=0,
                     raw_error_abs_sum=0., normalized_error_abs_sum=0.,
                     task_hard_agree=0, residual_huber_sum=0.)
        return stats
    s.require(arm == 'R_AB' and projection is not None, 'ARM_PROJECTION')
    return aligned.update(model, projection, opt, a, b, 'R', epoch, guard, cache, r, charge)
