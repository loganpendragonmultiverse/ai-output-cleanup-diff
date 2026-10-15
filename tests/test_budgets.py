import json
import os
from pathlib import Path

import pytest

from ai_output_cleanup_diff.cli import main
from ai_output_cleanup_diff.core import compare, render_json, render_markdown


def trees(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    return before, after


def test_exact_boundaries_and_total_exhaustion(tmp_path):
    before, after = trees(tmp_path)
    for root in (before, after):
        (root / "a.txt").write_bytes(b"1234")
        (root / "zero.txt").write_bytes(b"")
    report = compare(before, after, max_file_bytes=4, max_total_bytes=8)
    assert report["complete"] is True
    assert report["read_evidence"]["before_bytes_read"] == 4
    assert report["read_evidence"]["after_bytes_read"] == 4
    report = compare(before, after, max_total_bytes=4)
    assert report["complete"] is False
    assert report["counts"]["deleted"] == report["counts"]["renamed"] == 0
    assert any(item["reason"] == "total-budget" for item in report["unverified"])
    assert (
        sum(report["read_evidence"][key] for key in ["before_bytes_read", "after_bytes_read"]) == 4
    )
    assert compare(before, after)["read_evidence"]["mode"] == "unlimited"


def test_skipped_file_never_becomes_a_deletion_or_rename(tmp_path):
    before, after = trees(tmp_path)
    (before / "old.txt").write_text("PRIVATE-CONTENT")
    (after / "new.txt").write_text("PRIVATE-CONTENT")
    report = compare(before, after, max_file_bytes=3)
    assert report["counts"] == {"added": 0, "deleted": 0, "renamed": 0, "modified": 0}
    assert report["complete"] is False
    assert "PRIVATE-CONTENT" not in render_json(report) + render_markdown(report)
    assert (before / "old.txt").read_text() == "PRIVATE-CONTENT"
    assert compare(before, after, max_file_bytes=15)["counts"]["renamed"] == 1


def test_binary_only_absence_and_renames_are_unverified(tmp_path):
    before, after = trees(tmp_path)
    (before / "old.bin").write_bytes(b"secret\x00value")
    (after / "new.bin").write_bytes(b"secret\x00value")
    report = compare(before, after)
    assert report["counts"]["deleted"] == report["counts"]["renamed"] == 0
    assert len(report["unverified"]) == 2
    assert "secret" not in render_json(report) + render_markdown(report)


def test_symlink_and_unreadable_paths_do_not_prove_absence(tmp_path, monkeypatch):
    before, after = trees(tmp_path)
    (before / "file.txt").write_text("same")
    (after / "new.txt").write_text("same")
    try:
        (after / "file.txt").symlink_to(after / "new.txt")
    except OSError:
        pytest.skip("symlink creation unavailable")
    report = compare(before, after)
    assert report["counts"]["deleted"] == report["counts"]["renamed"] == 0
    assert any(x["reason"] == "symlink" for x in report["unverified"])
    (after / "file.txt").unlink()
    original = os.open

    def fail(path, *args, **kwargs):
        if Path(path).name == "new.txt":
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail)
    report = compare(before, after)
    assert not report["complete"]
    assert report["counts"]["deleted"] == report["counts"]["renamed"] == 0
    assert any(x["reason"] == "unreadable-file" for x in report["unverified"])


def test_directory_enumeration_failure_is_not_an_empty_tree(tmp_path, monkeypatch):
    before, after = trees(tmp_path)
    (before / "file.txt").write_text("content")
    original = os.walk

    def walk(root, **kwargs):
        if root == after:
            kwargs["onerror"](PermissionError(13, "denied", str(after)))
            return iter([])
        return original(root, **kwargs)

    monkeypatch.setattr(os, "walk", walk)
    report = compare(before, after)
    assert report["counts"]["deleted"] == 0
    assert not report["complete"]


def test_small_later_files_and_zero_budget(tmp_path):
    before, after = trees(tmp_path)
    for root in (before, after):
        (root / "a-large").write_text("long")
        (root / "b-small").write_text("x")
        (root / "c-zero").write_text("")
    report = compare(before, after, max_file_bytes=1, max_total_bytes=2)
    assert (
        report["read_evidence"]["before_bytes_read"]
        == report["read_evidence"]["after_bytes_read"]
        == 1
    )
    zero = compare(before, after, max_file_bytes=0, max_total_bytes=0)
    assert zero["read_evidence"]["before_bytes_read"] == 0
    assert all(x["path"] != "c-zero" for x in zero["unverified"])


@pytest.mark.parametrize("limit", [-1, True, 1.5, "4"])
def test_invalid_limits_reject(tmp_path, limit):
    before, after = trees(tmp_path)
    with pytest.raises(ValueError):
        compare(before, after, max_file_bytes=limit)
    with pytest.raises(ValueError):
        compare(before, after, max_total_bytes=limit)


def test_cli_reports_coverage_and_rejects_invalid_budget(tmp_path, capsys):
    before, after = trees(tmp_path)
    (before / "a").write_text("secret")
    assert main([str(before), str(after), "--max-total-bytes", "0", "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert not report["complete"]
    assert "secret" not in json.dumps(report)
    assert main([str(before), str(after), "--max-file-bytes", "-1"]) == 2


def test_exclusions_symlink_directory_and_invalid_utf8(tmp_path):
    before, after = trees(tmp_path)
    for root in (before, after):
        (root / "dist").mkdir()
        (root / "dist" / "ignored.txt").write_text("private")
        (root / "custom.txt").write_text("private")
    (before / "bad.bin").write_bytes(b"\xff")
    (after / "bad.bin").write_bytes(b"\xfe")
    report = compare(before, after, ["custom.txt"])
    assert report["modified"][0]["kind"] == "binary"
    assert report["read_evidence"]["before_bytes_read"] == 1
    try:
        (after / "linked").symlink_to(before, target_is_directory=True)
    except OSError:
        return
    report = compare(before, after, ["custom.txt"])
    assert any(
        item["path"] == "linked" and item["reason"] == "symlink" for item in report["unverified"]
    )


def test_changed_during_read_is_unverified(tmp_path, monkeypatch):
    before, after = trees(tmp_path)
    (before / "a").write_text("stable")
    original = os.fstat
    calls = 0

    class Changed:
        def __init__(self, value):
            self.st_size = value.st_size + 1
            self.st_mtime_ns = value.st_mtime_ns
            self.st_ctime_ns = value.st_ctime_ns

    def fstat(fd):
        nonlocal calls
        calls += 1
        value = original(fd)
        return Changed(value) if calls == 2 else value

    monkeypatch.setattr(os, "fstat", fstat)
    report = compare(before, after)
    assert not report["complete"]
    assert report["unverified"][0]["reason"] == "changed-during-read"
    assert report["deleted"] == []


def test_successful_markdown_output_contains_no_content(tmp_path):
    before, after = trees(tmp_path)
    (after / "file.txt").write_text("PRIVATE-SENTINEL")
    output = tmp_path / "report.md"
    assert main([str(before), str(after), "--output", str(output)]) == 0
    assert "PRIVATE-SENTINEL" not in output.read_text()
    assert "Read coverage" in output.read_text()


@pytest.mark.parametrize(
    "name, exclusions", [("dist", []), ("ignored", ["ignored/**"]), ("ignored", ["ignored"])]
)
def test_excluded_directory_symlinks_do_not_poison_rename_evidence(tmp_path, name, exclusions):
    before, after = trees(tmp_path)
    (before / "old.txt").write_text("same")
    (after / "new.txt").write_text("same")
    target = tmp_path / "excluded-target"
    target.mkdir()
    (target / "private.txt").write_text("PRIVATE-CONTENT")
    try:
        (after / name).symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable")
    report = compare(before, after, exclusions, max_file_bytes=4, max_total_bytes=8)
    assert report["complete"] is True
    assert report["unverified"] == []
    assert report["renamed"] == [{"from": "old.txt", "to": "new.txt", "bytes": 4}]
    assert report["counts"] == {"added": 0, "deleted": 0, "renamed": 1, "modified": 0}
    assert json.loads(render_json(report)) == report
    markdown = render_markdown(report)
    assert "Per-file budget: 4 bytes." in markdown
    assert "Combined budget: 8 bytes." in markdown
    assert "Actual bytes read: before 4; after 4; total 8." in markdown
    assert "PRIVATE-CONTENT" not in render_json(report) + markdown
    # Round-trip the exclusion on both sides as well.
    (before / name).symlink_to(target, target_is_directory=True)
    assert compare(before, after, exclusions)["renamed"] == report["renamed"]


def test_markdown_zero_and_unlimited_budgets_are_explicit(tmp_path):
    before, after = trees(tmp_path)
    unlimited = render_markdown(compare(before, after))
    assert "Per-file budget: unlimited." in unlimited
    assert "Combined budget: unlimited." in unlimited
    zero = render_markdown(compare(before, after, max_file_bytes=0, max_total_bytes=0))
    assert "Per-file budget: 0 bytes." in zero
    assert "Combined budget: 0 bytes." in zero
    assert "Actual bytes read: before 0; after 0; total 0." in zero
