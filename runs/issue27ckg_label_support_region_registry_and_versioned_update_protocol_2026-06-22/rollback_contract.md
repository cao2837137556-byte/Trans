# Rollback Contract v1

Every released model records:

- model version and parent model version;
- support-train view version and hash;
- region registry version;
- training configuration hash;
- evaluation report hash;
- release decision and timestamp.

Rollback restores the complete previous tuple, not only model weights:

```text
(model, support_train_view, registry, config, controller policy)
```

Archive events and rejected candidates are never deleted by rollback. They remain append-only evidence for later review.
