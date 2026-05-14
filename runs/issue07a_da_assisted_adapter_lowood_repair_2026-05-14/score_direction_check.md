# Score Direction Check

- dA cache uses the original anomaly score direction: higher means more anomalous.
- LogisticRegression adapters use `decision_function`; higher means more attack-like because attack supports are labeled positive.
