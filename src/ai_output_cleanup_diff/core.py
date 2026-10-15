from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import stat
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


def _inventory(
    root: Path, excludes: list[str], per_file: int | None, budget: dict[str, Any]
) -> tuple[dict[str, bytes], dict[str, str]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"not a directory or symlink root: {root}")
    result: dict[str, bytes] = {}
    skipped: dict[str, str] = {}

    def walk_error(error: OSError) -> None:
        try:
            relative = Path(error.filename or root).relative_to(root).as_posix()
        except ValueError:
            relative = "."
        skipped[relative] = "unreadable-directory"

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs.sort()
        files.sort()
        for name in dirs.copy():
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                skipped[relative] = "symlink"
                dirs.remove(name)
            elif any(fnmatch.fnmatch(relative + "/", pattern) for pattern in excludes):
                dirs.remove(name)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(relative, pattern) for pattern in excludes):
                continue
            if path.is_symlink():
                skipped[relative] = "symlink"
                continue
            try:
                descriptor = os.open(
                    path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                )
                with os.fdopen(descriptor, "rb") as stream:
                    initial = os.fstat(stream.fileno())
                    size = initial.st_size
                    if not stat.S_ISREG(initial.st_mode):
                        skipped[relative] = "non-regular"
                        continue
                    if per_file is not None and size > per_file:
                        skipped[relative] = "per-file-budget"
                        continue
                    if budget["remaining"] is not None and size > budget["remaining"]:
                        skipped[relative] = "total-budget"
                        continue
                    content = stream.read(size)
                    budget["read"] += len(content)
                    if budget["remaining"] is not None:
                        budget["remaining"] -= len(content)
                    final = os.fstat(stream.fileno())
                    if len(content) != size or (
                        initial.st_size,
                        initial.st_mtime_ns,
                        initial.st_ctime_ns,
                    ) != (final.st_size, final.st_mtime_ns, final.st_ctime_ns):
                        skipped[relative] = "changed-during-read"
                    else:
                        result[relative] = content
            except OSError:
                skipped[relative] = "unreadable-file"
    return result, skipped


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
    before_root: Path,
    after_root: Path,
    excludes: list[str] | None = None,
    *,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
) -> dict[str, Any]:
    patterns = [*DEFAULT_EXCLUDES, *(excludes or [])]
    for limit in (max_file_bytes, max_total_bytes):
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("read budgets must be non-negative integers or None (unlimited)")
    budget = {"remaining": max_total_bytes, "read": 0}
    before, before_skipped = _inventory(before_root, patterns, max_file_bytes, budget)
    before_read = budget["read"]
    after, after_skipped = _inventory(after_root, patterns, max_file_bytes, budget)
    unverified = [
        {"side": side, "path": path, "reason": reason}
        for side, skipped in (("before", before_skipped), ("after", after_skipped))
        for path, reason in sorted(skipped.items())
    ]
    before_names, after_names = set(before), set(after)
    deleted, added = before_names - after_names, after_names - before_names
    # Incomplete enumeration/read coverage cannot prove absence or an exact rename.
    safe_deleted, safe_added = set(), set()
    for side, names, content, own_skipped, other_skipped, safe in (
        ("before", deleted, before, before_skipped, after_skipped, safe_deleted),
        ("after", added, after, after_skipped, before_skipped, safe_added),
    ):
        for name in sorted(names):
            if (
                before_skipped
                or after_skipped
                or name in own_skipped
                or _text_changes(content[name], content[name]) is None
            ):
                unverified.append(
                    {"side": side, "path": name, "reason": "absence-or-content-unverified"}
                )
            else:
                safe.add(name)
    deleted, added = safe_deleted, safe_added
    renamed = []
    added_by_hash: dict[str, list[str]] = {}
    for name in sorted(added):
        added_by_hash.setdefault(_hash(after[name]), []).append(name)
    consumed_added = set()
    consumed_deleted = set()
    for old_name in sorted(deleted) if not unverified else []:
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
        "unverified": unverified,
        "complete": not before_skipped and not after_skipped and not unverified,
        "read_evidence": {
            "mode": "unlimited"
            if max_file_bytes is None and max_total_bytes is None
            else "bounded",
            "max_file_bytes": max_file_bytes,
            "max_total_bytes": max_total_bytes,
            "before_bytes_read": before_read,
            "after_bytes_read": budget["read"] - before_read,
        },
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
    lines.extend(
        [
            "",
            "## Read coverage",
            "",
            f"Complete: {report['complete']}; mode: {report['read_evidence']['mode']}.",
        ]
    )
    if report["unverified"]:
        lines.extend(["", "## Unverified", ""])
        lines.extend(
            f"- {item['side']} `{item['path']}`: {item['reason']}" for item in report["unverified"]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"
