# Changelog

## 1.1.0 - 2026-10-15

- Add optional per-file and combined read budgets with deterministic traversal and explicit unlimited defaults.
- Report skipped and unreadable paths as unverified; suppress absence and exact-rename claims on incomplete comparisons.
- Keep binary-only additions/deletions unverified and preserve content-free reports and read-only sources.

## 1.0.0 - 2026-07-26

- Added read-only before and after directory comparison.
- Added text line counts, binary-change labels, sizes, and hashes.
- Added exact-content rename detection and Markdown or JSON summaries.
