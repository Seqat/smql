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


def test_parse_from_alias():
    """Parse a from clause with an alias."""
    source = "from users as u\n"
    ast = parse_smql(source)
    assert ast.statements[0].source == "users"
    assert ast.statements[0].alias == "u"


def test_parse_query_return_fields():
    """Parse a query definition with return fields."""
    source = "query active_users() returns { id: int, name: string }\nfrom users\nfilter active == 1\nend\n"
    ast = parse_smql(source)
    query_def = ast.statements[0]
    assert query_def.name == "active_users"
    assert len(query_def.return_fields) == 2
    assert query_def.return_fields[0]["name"] == "id"
    assert query_def.return_fields[0]["type"] == "int"
    assert query_def.return_fields[1]["name"] == "name"
    assert query_def.return_fields[1]["type"] == "string"


def test_parse_from_subquery():
    """Parse a from clause containing a subquery pipeline."""
    source = "from (\n  from users\n  filter active == 1\n)\n"
    ast = parse_smql(source)
    from_clause = ast.statements[0]
    # Check that it's a FromSubquery and it contains pipeline steps
    assert from_clause.__class__.__name__ == "FromSubquery"
    assert len(from_clause.pipeline) == 2
    assert from_clause.pipeline[0].source == "users"

