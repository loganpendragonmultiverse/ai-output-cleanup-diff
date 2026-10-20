# Example

```bash
cleanup-diff raw-generated reviewed-final --output cleanup-summary.md
cleanup-diff raw-generated reviewed-final --exclude "fixtures/**" --format json
```

For an exact four-byte synthetic file on each side, use `--max-file-bytes 5 --max-total-bytes 9` to leave EOF allowance; actual content consumption remains eight bytes. Exact exhausted budgets are unverified.
