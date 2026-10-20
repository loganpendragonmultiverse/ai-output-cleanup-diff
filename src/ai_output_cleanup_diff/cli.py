from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import compare, render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize cleanup between generated and reviewed folders."
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--max-file-bytes", type=int, help="maximum bytes per file; omitted means unlimited"
    )
    parser.add_argument(
        "--max-total-bytes",
        type=int,
        help="combined read budget across before then after; omitted means unlimited",
    )
    args = parser.parse_args(argv)
    try:
        report = compare(
            args.before,
            args.after,
            args.exclude,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )
        rendered = render_json(report) if args.format == "json" else render_markdown(report)
        if args.output:
            if args.output.exists() or args.output.is_symlink():
                raise ValueError(f"output already exists: {args.output}")
            with args.output.open("x", encoding="utf-8") as output:
                output.write(rendered)
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0 if report["complete"] else 1
