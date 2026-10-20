# Testing

Run `python -m pip install -e ".[dev]"`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m pytest`, and `python -m build`. Keep the 90% branch-aware coverage floor and native Python/OS matrix.

Fixtures cover content-free reports, budgets and exclusions, unreadable/changed paths, binary uncertainty, exact-limit exhaustion, observed EOF, zero-size virtual metadata, actual-byte accounting and preserved raced/dangling output destinations. Synthetic fixture data only.

Install each exact-tag wheel and source distribution into a fresh environment outside the checkout. Confirm imports come from site-packages, run the full tests and CLI examples, and verify all four authority documents are shipped in the source distribution. Native CI does not imply native installed-artifact acceptance.

Exit statuses: 0 complete comparison, 1 incomplete/unverified evidence, 2 invalid input or output failure. Selected root symlinks are refused; ordinary ancestor path aliases are allowed. Descendant links are skipped and unverified. Direct API exclusions must be a list of strings. Markdown filenames use variable-length code delimiters and visible control-character escapes.

Installed distributions must include README, DEVELOPMENT, TESTING, CHANGELOG, LICENSE and the example guide under share/doc. Inspect both wheel metadata/data payload and source-distribution contents before release.
