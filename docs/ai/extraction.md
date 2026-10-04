# Extraction

DIAR uses canonical skills, aliases, regex/context checks, and restricted typo matching; no trained neural classifier is used.

Evidence distinguishes claimed, planned, negated, and uncertain mentions. Only supported positive claims count. Ambiguous words need technical or skill-list context. Heuristics may still misread complex prose.

Employment extraction uses relevant sections, excludes education dates, merges overlaps, and uses the current date for ongoing work. Ambiguous or absent experience remains unknown.

PDFs must contain readable text. Invalid, encrypted, textless, and oversized files receive clear reasons; OCR is deferred.

GitHub data excludes forks consistently and paginates to the configured cap. Recent pushes are an activity proxy. Failures/truncation stay visible. Repository languages/text do not establish verified proficiency.

See [data model](../architecture/data-model.md), [dataset guide](../testing/dataset-guide.md), and [privacy](../privacy/data-handling.md).
