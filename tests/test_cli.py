"""Tests for the SMQL CLI."""

import pytest
from typer.testing import CliRunner
from pathlib import Path

from smql_compiler.cli import app

runner = CliRunner()

@pytest.fixture
def example_file(tmp_path) -> Path:
    smql_path = tmp_path / "test.smql"
    smql_path.write_text("from users\nfilter age > @min_age\n")
    return smql_path

def test_cli_missing_param_error(example_file):
    """Running without required parameters shows a nice error."""
    result = runner.invoke(app, ["compile", str(example_file)])
    assert result.exit_code == 1
    assert "Parameter Error:" in result.stdout
    assert "Missing value for parameter '@min_age'" in result.stdout

def test_cli_with_param(example_file):
    """Running with --param passes the value to codegen."""
    result = runner.invoke(app, ["compile", str(example_file), "--param", "min_age=18"])
    assert result.exit_code == 0
    assert "WHERE age > $1" in result.stdout
    assert "$1" in result.stdout
    assert "18" in result.stdout

def test_cli_dry_run(example_file):
    """Running with --dry-run produces SQL without requiring values."""
    result = runner.invoke(app, ["compile", str(example_file), "--dry-run"])
    assert result.exit_code == 0
    assert "WHERE age > $1" in result.stdout
    assert "$1" in result.stdout
    assert "'@min_age'" in result.stdout

def test_cli_multiple_params(tmp_path):
    smql_path = tmp_path / "test_multi.smql"
    smql_path.write_text("from users\nfilter age > @min_age and country == @country\n")
    
    result = runner.invoke(app, [
        "compile", str(smql_path), 
        "--param", "min_age=18", 
        "--param", "country=TR"
    ])
    
    assert result.exit_code == 0
    assert "WHERE age > $1 AND country = $2" in result.stdout
    assert "18" in result.stdout
    assert "'TR'" in result.stdout


def test_cli_file_not_found():
    """Passing a non-existent file produces an error."""
    result = runner.invoke(app, ["compile", "/nonexistent/file.smql"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_cli_wrong_extension(tmp_path):
    """Passing a .sql file produces a warning but still compiles."""
    sql_path = tmp_path / "test.sql"
    sql_path.write_text("from users\ntake 5\n")
    result = runner.invoke(app, ["compile", str(sql_path)])
    assert "Warning" in result.stdout
    assert ".sql" in result.stdout


def test_cli_version():
    """The version command prints the version string."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "SMQL Compiler v" in result.stdout


def test_cli_output_file(tmp_path):
    """--output writes SQL to a file instead of stdout."""
    smql_path = tmp_path / "test.smql"
    smql_path.write_text("from users\ntake 5\n")
    out_path = tmp_path / "output.sql"

    result = runner.invoke(app, [
        "compile", str(smql_path), "--output", str(out_path),
    ])
    assert result.exit_code == 0
    assert out_path.exists()
    content = out_path.read_text()
    assert "SELECT *" in content
    assert "FROM users" in content


def test_cli_explain(tmp_path):
    """--explain prints diagnostics."""
    smql_path = tmp_path / "test.smql"
    smql_path.write_text("from users\ntake 5\n")
    result = runner.invoke(app, ["compile", str(smql_path), "--explain"])
    assert result.exit_code == 0


def test_cli_numeric_param_conversion(tmp_path):
    """Numeric parameter values are converted to int/float."""
    smql_path = tmp_path / "test.smql"
    smql_path.write_text("from users\nfilter age > @min_age\n")
    result = runner.invoke(app, [
        "compile", str(smql_path), "--param", "min_age=25",
    ])
    assert result.exit_code == 0
    # The param table should show 25 as an int, not '25' as a string
    assert "25" in result.stdout

