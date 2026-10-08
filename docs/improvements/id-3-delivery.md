# ID 3: Skill context and overlapping aliases

Status: implemented on `fix/analysis-evidence-foundation`; awaiting commit/review/merge.
Author for commit commands: raveesha2002.
Starting commit: `0839edd`; PR and merge commit: pending.

## Problem and final behavior

Whitespace normalization previously removed line boundaries, allowing negation or
learning intent to affect an unrelated skill on the next line. Newline boundaries
are preserved during normalization. Existing sentence/clause delimiters and contrast
handling continue to apply. Longest exact aliases take precedence over overlapping
matches, so one phrase does not count twice or claim an embedded shorter skill.
Common learning/context words are excluded from fuzzy typo matching; specifically,
"learn" must not become an accidental "sklearn" skill match.

Affected: extraction.py and focused synthetic tests. Dictionary aliases, typo
tolerance and claimed/uncertain/planned/negated categories remain supported.
Corrected evidence can intentionally change skill scores and recommendations; no
scoring formula or ML model was replaced.

## Verification and limits

See `id-2-delivery.md` for shared group results. New tests cover negated, planned and
uncertain Java followed by claimed Python on another line, and overlapping aliases.
Existing sentence/contrast and frequency-cap fixtures remain in the regression suite.

Extraction is still heuristic; complicated prose and multi-clause punctuation can
be ambiguous. No independent skill verification or new NLP model is introduced.

## Rollback

Revert the group PR after checking dependencies. Previously saved reports retain
their original extracted evidence; rollback does not regenerate historical results.
