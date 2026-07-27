from __future__ import annotations

import fnmatch
import hashlib
import json
from collections import Counter
from difflib import ndiff
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDES = (
    ".git/**",
    "**/.git/**",
    ".venv/**",
    "**/.venv/**",
    "node_modules/**",
    "**/node_modules/**",
    "build/**",
    "dist/**",
)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inventory(root: Path, excludes: list[str]) -> dict[str, bytes]:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    result = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(relative, pattern) for pattern in excludes):
            continue
        result[relative] = path.read_bytes()
    return result


def _text_changes(before: bytes, after: bytes) -> tuple[int, int] | None:
    if b"\0" in before or b"\0" in after:
        return None
    try:
        old = before.decode("utf-8").splitlines()
        new = after.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    changes = list(ndiff(old, new))
    return sum(line.startswith("+ ") for line in changes), sum(
        line.startswith("- ") for line in changes
    )


def compare(
    before_root: Path, after_root: Path, excludes: list[str] | None = None
) -> dict[str, Any]:
    patterns = [*DEFAULT_EXCLUDES, *(excludes or [])]
    before = _inventory(before_root, patterns)
    after = _inventory(after_root, patterns)
    before_names, after_names = set(before), set(after)
    deleted, added = before_names - after_names, after_names - before_names
    renamed = []
    added_by_hash: dict[str, list[str]] = {}
    for name in added:
        added_by_hash.setdefault(_hash(after[name]), []).append(name)
    consumed_added = set()
    consumed_deleted = set()
    for old_name in sorted(deleted):
        matches = added_by_hash.get(_hash(before[old_name]), [])
        target = next((name for name in matches if name not in consumed_added), None)
        if target:
            renamed.append({"from": old_name, "to": target, "bytes": len(before[old_name])})
            consumed_deleted.add(old_name)
            consumed_added.add(target)
    changes = []
    for name in sorted(before_names & after_names):
        if before[name] == after[name]:
            continue
        text = _text_changes(before[name], after[name])
        changes.append(
            {
                "path": name,
                "kind": "text" if text else "binary",
                "added_lines": text[0] if text else None,
                "removed_lines": text[1] if text else None,
                "before_bytes": len(before[name]),
                "after_bytes": len(after[name]),
                "before_sha256": _hash(before[name]),
                "after_sha256": _hash(after[name]),
            }
        )
    final_added = sorted(added - consumed_added)
    final_deleted = sorted(deleted - consumed_deleted)
    extensions = Counter(Path(item["path"]).suffix.casefold() or "[none]" for item in changes)
    return {
        "version": 1,
        "counts": {
            "added": len(final_added),
            "deleted": len(final_deleted),
            "renamed": len(renamed),
            "modified": len(changes),
        },
        "added": final_added,
        "deleted": final_deleted,
        "renamed": renamed,
        "modified": changes,
        "modified_extensions": dict(sorted(extensions.items())),
    }


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# AI Output Cleanup Diff",
        "",
        f"**{counts['modified']} modified · {counts['added']} added · {counts['deleted']} deleted · {counts['renamed']} renamed**",
        "",
    ]
    if report["modified"]:
        lines.extend(["## Modified", ""])
        for item in report["modified"]:
            detail = (
                f"+{item['added_lines']} / -{item['removed_lines']} lines"
                if item["kind"] == "text"
                else "binary content changed"
            )
            lines.append(
                f"- `{item['path']}` — {detail}; {item['before_bytes']} → {item['after_bytes']} bytes"
            )
    if report["renamed"]:
        lines.extend(["", "## Exact-content renames", ""])
        lines.extend(f"- `{item['from']}` → `{item['to']}`" for item in report["renamed"])
    for label in ("added", "deleted"):
        if report[label]:
            lines.extend(["", f"## {label.title()}", ""])
            lines.extend(f"- `{name}`" for name in report[label])
    return "\n".join(lines).rstrip() + "\n"


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"
