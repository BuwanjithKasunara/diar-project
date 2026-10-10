# Decision: bounded public repository file privacy review

Status: implemented on `feat/repository-file-privacy`; not yet committed/merged.
Date: 2026-10-09. Improvement ID: 9. Author for commit commands: charya19.

## Context and decision

The original privacy realignment intentionally reused public GitHub metadata and
supplied text. It did not fetch file contents; its original implementation plan
remains a historical record of that scope. The user subsequently requested a
bounded extension that inspects public repository contents before broader UI work.

Add an optional `scan_repository_files` analysis form boolean, default false.
The existing metadata-only workflow performs no extra file requests. An enabled
scan reviews a fixed root-file allowlist from up to five already fetched public
repositories, including forks. It never claims to inspect a whole repository.
Collection is independent of desired visibility: unnecessary disclosures can be
reviewed under any goal. Career/ML inputs and scores do not include downloaded text.

## Collection and revision strategy

Resolve the repository's default-branch reference, then the current Git commit's
root tree SHA, then a nonrecursive Git tree. This accesses current revision
metadata to locate the tree; it does not scan commit messages/authors or history.
Read selected blobs by SHA, ignoring all API-provided URLs. A recorded commit SHA
identifies the contents reviewed even if the default branch subsequently changes.

Only root `README.md`, `README.markdown`, `README.rst`, `README.txt` or `README`
(case-insensitive) is selected, in that preference order. Choose one README,
then root `CONTRIBUTING.md` and `SECURITY.md`. Alternate READMEs and file-limit
exclusions are reported as skipped. Missing supported filenames are reported.
`docs/README.md`, `.github/README.md`, source files and nested documents are excluded.

Git tree modes distinguish regular blobs from symlinks, directories and submodules.
Only regular files are fetched. No links, symlink targets, private repositories,
archives, binary content, issue/PR text or other folders are followed.
An allowlisted README can contain generated/sample content; origin/ownership of
such text is not inferred from a pattern match.

The scanner requires explicit `private=false` and validated repository identifiers
from the fetched API listing. It constructs fixed `https://api.github.com` paths,
escapes the branch, validates SHA syntax, disables redirects, makes anonymous
requests and does not use tokens/.netrc or environment authentication/proxies.
This may need a separately designed transport configuration on networks requiring
a proxy. It never broadens a token's access to private contents.

Technical references: GitHub's [Git references](https://docs.github.com/en/rest/git/refs),
[Git commits](https://docs.github.com/en/rest/git/commits),
[Git trees](https://docs.github.com/en/rest/git/trees) and
[Git blobs](https://docs.github.com/en/rest/git/blobs) APIs.

## Final limits

| Limit | Value |
|---|---|
| Repositories selected | First 5 from existing fetched order (updated first), including forks |
| Files per repository | At most 3 root allowlisted files |
| Decoded bytes per file | 100 KiB |
| Aggregate decoded bytes | 1 MiB, including rejected decoded text |
| Additional HTTP requests | 25, including discovery, failures and blob reads |
| Streamed JSON response body | 256 KiB per response |
| Request response budget | 5 seconds, checked around I/O and streamed chunks |
| Scan elapsed budget | 20 seconds, shortened to reserve 3 seconds before the analysis construction deadline |
| Findings retained | Existing 50-evidence aggregate report cap; omission counts disclosed |

Size metadata is checked before download. Streamed response bodies are bounded;
base64 length/decoded size are checked before accepting text. Only UTF-8/UTF-8 BOM
text without binary control characters is reviewed. There are no retries, paginated
tree walks or repository clones. Limits are prototype defaults, not capacity claims.

Timeouts are cooperative around blocking I/O, not a guarantee that operating-system
DNS/socket work or Python threads are forcibly stopped at the exact deadline.
Late responses are rejected. The existing 40-second backend construction deadline
remains the final response bound and prevents saving late worker results.

The 25-request cap can stop discovery before all three files in the fifth selected
repository are fetched (each repository needs three discovery requests). That is
intentional and appears as partial/unavailable coverage, never silent completion.

## Evidence, masking and advice

Reuse email, phone, street-address and date-of-birth detection. Scan whole text so
labels may span lines; map match offsets to one-based source lines. Preserve
possible-phone labels and existing exclusions for dates/versions/career metrics.
No secret/API-key/password detector or independent ownership classifier is added.

The new `github_repository_file` evidence source records a masked repository name,
root path, line number, commit revision, masked excerpt and evidence ID. Mask all
supported matches before cropping, plus personal patterns in context labels. Raw
file text/base64 and commit/tree responses remain transient and are not persisted
or included in application error messages, including under report policy `none`.
Names or other identifying prose can remain in masked excerpts; masking is not anonymity.

No clickable source URLs are stored in this stage. File/path/line/revision context
allows manual review without introducing URL/contact/handle masking exceptions.
Future links or exports must obey the saved-report protection policy.

Recommendations group file findings by kind and list affected repository/file/line
locations. They ask the user to confirm whether a match is real personal information,
review whether public disclosure is needed, and edit/replace unnecessary details.
Professional contacts, contributor addresses and example values are candidates for
review, not automatically vulnerabilities belonging to the account owner.
Editing the latest file cannot remove history, forks, caches or external copies.

## Coverage, failures and compatibility

Add optional `coverage.github_repository_files` with enabled/status, repository/file
counts, revision, per-file checked/skipped/not-found reasons, byte/request usage and
stop reason. Disabled, unavailable, partial, checked and no-supported-files are
distinct. Checked means the selected allowed contents were checked, not the account
or whole repository. Existing GitHub metadata coverage remains independent.

Existing resume/LinkedIn/metadata evidence keeps its existing allocation/order;
file evidence uses the remaining report slots. All file findings are counted even
when capped, and omissions remain explicit. One failing file does not discard
previous findings; rate limits/budget expiry stop additional requests gracefully.
An unavailable or missing README is not described as a clean file scan.

Enabled scans replace blanket metadata-only exclusions with exact file scope and
remaining exclusions. Old reports retain their original limits and display fallback;
there is no historical rescan, database migration or raw-source addition.
Saved masking, deletion and prior-request recovery continue to apply.

## Verification and rollback

See [ID 9 delivery record](../improvements/id-9-delivery.md) for final commands/results
and browser checks. Tests use synthetic public API responses and isolated databases,
not real personal repositories or tokens. Revert this stage's PR if needed, checking
later UI dependencies first. Reverting code does not erase earlier report findings
or remove information from GitHub. Raw files are never retained to reprocess.
