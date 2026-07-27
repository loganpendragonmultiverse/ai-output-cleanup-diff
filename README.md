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
