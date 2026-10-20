# AI Output Cleanup Diff

[![CI](https://github.com/loganpendragonmultiverse/ai-output-cleanup-diff/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/ai-output-cleanup-diff/actions/workflows/ci.yml)

AI Output Cleanup Diff summarizes the changes between a raw generated folder and its reviewed final version. It distinguishes added, deleted, modified, and exact-content renamed files and reports text line counts, sizes, and SHA-256 evidence without embedding file contents.

## Three-minute start

```bash
python -m pip install .
cleanup-diff raw-generated reviewed-final --output cleanup-summary.md
cleanup-diff raw-generated reviewed-final --format json
```

The comparison is read-only, skips symlinks and common generated directories, recognizes UTF-8 text, treats other changed content as binary, and refuses existing output files.

The report describes observable file differences; it cannot determine which edits were made by a person, whether the original was AI-generated, or whether a change improved quality. Exact-content rename detection is hash-based. Requires Python 3.10 or newer.

Part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Licensed under the [MIT License](LICENSE).

## Read budgets and incomplete evidence

`cleanup-diff raw-generated reviewed-final --max-file-bytes 1048576 --max-total-bytes 16777216 --format json`
limits bytes read per file and across both trees. Non-negative integers include zero;
omitting a limit means unlimited (the legacy default). Traversal is deterministic,
with before read first, sorted directories and files. Oversized files are skipped
without reading; smaller later files can still fit. Verification requires observed EOF.
Exact budget exhaustion remains unverified, including zero-byte budgets; leave at
least one byte of allowance for an EOF read (which consumes zero content bytes). JSON and Markdown retain budgets, actual bytes read and unverified paths.

Skipped, unreadable, changed-during-read, non-regular and symlink paths are unverified.
An incomplete inventory prevents absence and exact-rename claims; readable same-path
files can still be compared. Binary-only added/deleted paths are unverified and do not
become exact renames. Same-path binary modifications still retain sizes and hashes.
Intentional exclusions define the comparison scope. A missing or symlink root rejects.
Sources are never modified and contents never appear in reports. Filenames and hashes
are still visible. This is a sequential observation, not an atomic filesystem snapshot;
external changes after reading are outside its evidence.

Reports require a new destination and protect ordinary existing files, dangling
symlinks and concurrent regular-file creation using an explicit guard and exclusive
creation. This is not protection against hostile concurrent filesystem mutation.
See [DEVELOPMENT.md](DEVELOPMENT.md) and [TESTING.md](TESTING.md).

Exit statuses: 0 complete comparison, 1 incomplete/unverified evidence, 2 invalid input or output failure. Selected root symlinks are refused; ordinary ancestor path aliases are allowed. Descendant links are skipped and unverified. Direct API exclusions must be a list of strings. Markdown filenames use variable-length code delimiters and visible control-character escapes.
