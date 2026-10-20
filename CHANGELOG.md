# Changelog

## 1.1.1 - 2026-10-20

- Require observed EOF without overspending read budgets; exact exhaustion remains unverified, including zero-byte limits.
- Read in bounded chunks and reject content inconsistent with reported file size.
- Preserve dangling symbolic links and concurrent report files with exclusive output creation.
- Validate API exclusions, render literal Markdown filenames and return status 1 for incomplete evidence.
- Ship development and source/installed-artifact testing guidance.

## 1.1.0 - 2026-10-15

- Add optional per-file and combined read budgets with deterministic traversal and explicit unlimited defaults.
- Report skipped and unreadable paths as unverified; suppress absence and exact-rename claims on incomplete comparisons.
- Apply directory exclusions before recording symlink uncertainty, and display numeric budgets and actual bytes read in Markdown.
- Keep binary-only additions/deletions unverified and preserve content-free reports and read-only sources.

## 1.0.0 - 2026-07-26

- Added read-only before and after directory comparison.
- Added text line counts, binary-change labels, sizes, and hashes.
- Added exact-content rename detection and Markdown or JSON summaries.
