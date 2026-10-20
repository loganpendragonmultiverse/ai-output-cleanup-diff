import os
from types import SimpleNamespace

import pytest

from ai_output_cleanup_diff import core
from ai_output_cleanup_diff.cli import main


def roots(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    return before, after


def test_exact_budget_requires_eof_allowance(tmp_path):
    before, after = roots(tmp_path)
    (before / "old").write_bytes(b"same")
    (after / "new").write_bytes(b"same")
    for kwargs in ({"max_file_bytes": 4}, {"max_total_bytes": 8}):
        report = core.compare(before, after, **kwargs)
        assert not report["complete"]
        assert report["counts"]["renamed"] == 0
        assert (
            sum(report["read_evidence"][k] for k in ("before_bytes_read", "after_bytes_read")) <= 8
        )
    report = core.compare(before, after, max_file_bytes=5, max_total_bytes=9)
    assert report["complete"] and report["counts"]["renamed"] == 1


def test_empty_file_needs_positive_eof_allowance(tmp_path):
    before, after = roots(tmp_path)
    (before / "empty").touch()
    assert not core.compare(before, after, max_total_bytes=0)["complete"]
    report = core.compare(before, after, max_total_bytes=1)
    assert report["complete"] and report["read_evidence"]["before_bytes_read"] == 0


def test_virtual_size_cannot_be_verified_or_overspend(tmp_path, monkeypatch):
    before, after = roots(tmp_path)
    (before / "old").write_bytes(b"PRIVATE")
    (after / "new").write_bytes(b"PRIVATE")
    real = os.fstat

    def zero_size(fd):
        value = real(fd)
        return SimpleNamespace(
            st_mode=value.st_mode,
            st_size=0,
            st_mtime_ns=value.st_mtime_ns,
            st_ctime_ns=value.st_ctime_ns,
        )

    monkeypatch.setattr(os, "fstat", zero_size)
    report = core.compare(before, after)
    assert not report["complete"] and report["counts"]["renamed"] == 0
    assert "PRIVATE" not in core.render_json(report)
    assert report["read_evidence"]["before_bytes_read"] == 7
    bounded = core.compare(before, after, max_file_bytes=2, max_total_bytes=3)
    assert bounded["read_evidence"]["before_bytes_read"] == 2
    assert bounded["read_evidence"]["after_bytes_read"] == 1
    assert not bounded["complete"]


def test_raced_output_is_preserved(tmp_path, monkeypatch):
    before, after = roots(tmp_path)
    output = tmp_path / "report"
    real = core.compare

    def race(*a, **kw):
        report = real(*a, **kw)
        output.write_text("concurrent")
        return report

    monkeypatch.setattr("ai_output_cleanup_diff.cli.compare", race)
    assert main([str(before), str(after), "--output", str(output)]) == 2
    assert output.read_text() == "concurrent"


def test_dangling_output_is_preserved(tmp_path):
    before, after = roots(tmp_path)
    output, target = tmp_path / "report", tmp_path / "missing"
    try:
        output.symlink_to(target)
    except OSError:
        pytest.skip("symlink unavailable")
    assert main([str(before), str(after), "--output", str(output)]) == 2
    assert output.is_symlink() and not target.exists()


@pytest.mark.parametrize("value", ["dist/**", [1], [True]])
def test_excludes_type_rejects(tmp_path, value):
    before, after = roots(tmp_path)
    with pytest.raises(ValueError, match="excludes"):
        core.compare(before, after, excludes=value)


def test_markdown_literal_names():
    assert core._filename("a```b\n## forged") == "```` a```b\\u000a## forged ````"
    assert core._filename("plain") == "` plain `"
