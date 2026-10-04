# Data handling

DIAR is a local single-user prototype. Inputs and evidence can contain personal information; use synthetic examples for testing/demonstration.

Analysis does not automatically persist. Explicit saving retains report JSON, including extracted excerpts, in SQLite. Reports can be opened/deleted. A report may contain sensitive content even without retaining the PDF file.

Private résumé contact details are not evidence of public exposure. GitHub is public API data; pasted LinkedIn visibility is unverified unless explicitly supplied. Visibility choices affect suggestions, not external platform access controls.

GitHub requests send the username to GitHub and may use a backend token. Never expose tokens to the browser or repository. LinkedIn credentials are not collected.

CORS is not authentication. No accounts or ownership enforcement exist; shared hosting is deferred. Deleting a row does not guarantee forensic erasure from database files or backups.
