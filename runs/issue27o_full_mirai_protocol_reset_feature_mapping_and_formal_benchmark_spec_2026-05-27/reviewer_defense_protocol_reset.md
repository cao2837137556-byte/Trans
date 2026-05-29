# Reviewer Defense: Protocol Reset

**Q1: Did you tune on full Mirai and then test on it?**
We explicitly mark issue20-27n as exploration. The reset benchmark retrains every method under one split and does not call full Mirai external or unseen.

**Q2: Why is full Mirai still valid?**
It is valid as a within-dataset benchmark after protocol reset, not as an external test.

**Q3: What about my_gold prior use?**
It is disclosed as exploration-used source. It motivates the reset rather than invalidating the dataset.

**Q4: Can anonymous clean115 support claims?**
It can support fair within-dataset model comparisons if named as anonymous clean115. It cannot support restored115/common100 semantic claims.

**Q5: Are old baseline failures final?**
No. All baselines must be rerun under the reset protocol.
