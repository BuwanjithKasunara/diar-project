# Data handling

DIAR is a local single-user prototype. Inputs and evidence can contain personal information; use synthetic examples for testing/demonstration.

Analysis does not automatically persist. Explicit saving retains report JSON, including extracted excerpts and GitHub README provenance, in SQLite. Reports can be opened/deleted. A report may contain sensitive content even without retaining the PDF or full README text.

Private résumé contact details are not evidence of public exposure. GitHub is public API data; pasted LinkedIn visibility is unverified unless explicitly supplied. Visibility choices affect suggestions, not external platform access controls.

GitHub requests send the username and selected repository/README paths to GitHub and may use a backend token. Never expose tokens to the browser or repository. Collection is bounded to owned public non-fork repository metadata and selected READMEs; it does not inspect private work, organisation-owned work, or third-party contribution history. LinkedIn credentials are not collected.

Evidence excerpts are truncated and exist to explain a match, not to reproduce source documents. Version 3 records source failures and scope limitations rather than treating unavailable data as weakness. Legacy report JSON remains stored as originally submitted and is not enriched or rescored later.

CORS is not authentication. No accounts or ownership enforcement exist; shared hosting is deferred. Deleting a row does not guarantee forensic erasure from database files or backups.

