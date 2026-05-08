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
