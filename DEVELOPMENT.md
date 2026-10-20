# Development

Preserve content-free reports, explicit uncertainty, strict actual-byte budgets and read-only sources. Whole UTF-8 contents are retained for line comparison; budgets limit input bytes, not all Python/diff overhead. This is sequential observation, not a filesystem snapshot.

Use an isolated environment: `python -m pip install -e ".[dev]"`. Run Ruff formatting/lint, the complete coverage-gated pytest suite and `python -m build`. Changes require independent review, protected native CI/main checks and exact-tag installed wheel/source-distribution acceptance.

EOF must be observed without exceeding either budget. A zero or exact exhausted budget is unverified; valid empty files need positive allowance but charge zero bytes. Never infer additions, deletions or renames from incomplete evidence.

Exit statuses: 0 complete comparison, 1 incomplete/unverified evidence, 2 invalid input or output failure. Selected root symlinks are refused; ordinary ancestor path aliases are allowed. Descendant links are skipped and unverified. Direct API exclusions must be a list of strings. Markdown filenames use variable-length code delimiters and visible control-character escapes.
