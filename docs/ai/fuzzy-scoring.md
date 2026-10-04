# Capability evidence scoring

Report version 3 scores benchmark evidence, not a person's overall skill. Each weighted capability contains an any-of set of canonical concepts. Its satisfaction is the strongest supporting evidence strength for any member, so repeated keywords and multiple aliases do not accumulate credit. The benchmark evidence score is the sum of `capability weight × satisfaction` and remains in `[0, 1]`.

Capability state follows the strongest usable evidence:

- `evidenced`: strength at least `0.6`.
- `weakly_evidenced`: strength greater than zero but below `0.6`.
- `not_observed`: usable relevant sources were analysed without a match.
- `not_assessed`: relevant evidence was unavailable.
- `explicit_gap`: the person explicitly states the capability is absent.

Fuzzy membership degrees remain in `assessment.benchmark_evidence` under collapsed method details. They explain how the numeric evidence score relates to the legacy membership functions; the public result does not select a `low`, `moderate`, or `strong` winner. Memberships are neither confidence probabilities nor probabilities of competence.

`assessment.source_scope` reports source availability separately from evidence. `assessment.github_portfolio_recency` reports raw owned-public-repository counts and the most recent repository push timestamp; it has no activity score or `active`/`inactive` label. An injected `as_of` date defines the recency window for deterministic tests.

[fuzzy_logic.py](../../backend/app/modules/fuzzy_logic.py) owns exact membership boundaries. Test zero/full evidence, thresholds, unavailable evidence, duplicate invariance, and injected dates. Do not claim empirical calibration without held-out evaluation.

