# Evidence-Gated Promotion Interpretation

This run is not continual learning and not fully automatic routing. It asks whether a small, explicit evidence budget can support promotion from V1 to V2 when fully automatic proxy signals are insufficient.

Evidence-gated promotion is safer than pure continual adaptation because a challenger must pass a low-alert OOD validation gate and an explicit confirmed-attack evidence gate before promotion. Review samples are not free and are not assumed to be attacks; they are a bounded evidence acquisition cost.
