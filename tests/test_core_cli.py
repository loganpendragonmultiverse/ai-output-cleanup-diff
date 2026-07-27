import json

import pytest

from ai_output_cleanup_diff.cli import main
from ai_output_cleanup_diff.core import compare, render_markdown


def test_compare_changes_and_renames(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    (after / "app.py").write_text("one\nreviewed\n", encoding="utf-8")
    (before / "old.txt").write_text("same", encoding="utf-8")
    (after / "new.txt").write_text("same", encoding="utf-8")
    (before / "removed.md").write_text("gone", encoding="utf-8")
    (after / "added.md").write_text("new", encoding="utf-8")
    report = compare(before, after)
    assert report["counts"] == {"added": 1, "deleted": 1, "renamed": 1, "modified": 1}
    assert report["modified"][0]["added_lines"] == 1
    assert "Exact-content renames" in render_markdown(report)


def test_binary_and_validation(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "asset.bin").write_bytes(b"a\0b")
    (after / "asset.bin").write_bytes(b"c\0d")
    assert compare(before, after)["modified"][0]["kind"] == "binary"
    with pytest.raises(ValueError, match="directory"):
        compare(tmp_path / "missing", after)


def test_cli_json_and_safe_output(tmp_path, capsys):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (after / "new.txt").write_text("new", encoding="utf-8")
    assert main([str(before), str(after), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["counts"]["added"] == 1
    output = tmp_path / "report.md"
    output.write_text("keep", encoding="utf-8")
    assert main([str(before), str(after), "--output", str(output)]) == 2
