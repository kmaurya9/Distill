from click.testing import CliRunner

from distill.cli import main


def test_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0


def test_help_lists_commands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "index" in result.output
    assert "serve" in result.output


def test_index_command_reports_real_counts(tmp_path):
    (tmp_path / "a.py").write_text("def helper():\n    return 1\n")
    db_path = tmp_path / "graph.db"

    result = CliRunner().invoke(main, ["index", str(tmp_path), "--db", str(db_path)])

    assert result.exit_code == 0
    assert "new files: 1" in result.output
    assert db_path.exists()


def test_reindexing_unchanged_repo_reports_zero_changes(tmp_path):
    (tmp_path / "a.py").write_text("def helper():\n    return 1\n")
    db_path = tmp_path / "graph.db"
    runner = CliRunner()

    runner.invoke(main, ["index", str(tmp_path), "--db", str(db_path)])
    result = runner.invoke(main, ["index", str(tmp_path), "--db", str(db_path)])

    assert result.exit_code == 0
    assert "new files: 0" in result.output
    assert "changed files: 0" in result.output
    assert "unchanged files: 1" in result.output
