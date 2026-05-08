"""Tests for the SMQL parser."""

from smql_compiler.parser import parse_smql, get_parser
from smql_compiler.ast import Program, FromClause, FilterClause, TakeClause


def test_parser_loads_grammar():
    """Ensure the Lark parser can be instantiated."""
    parser = get_parser()
    assert parser is not None


def test_parse_simple_from():
    """Parse a minimal SMQL pipeline."""
    source = "from users\nfilter age > 18\ntake 10\n"
    ast = parse_smql(source)
    assert ast is not None
    assert isinstance(ast, Program)
    assert len(ast.statements) == 3
    assert isinstance(ast.statements[0], FromClause)
    assert ast.statements[0].source == "users"
    assert isinstance(ast.statements[1], FilterClause)
    assert isinstance(ast.statements[2], TakeClause)
    assert ast.statements[2].count == 10


def test_parse_parameterized_filter():
    """Parse a query with a parameter."""
    source = "from users\nfilter age > @min_age\ntake 5\n"
    ast = parse_smql(source)
    assert ast is not None
    assert isinstance(ast, Program)
    assert len(ast.statements) == 3
