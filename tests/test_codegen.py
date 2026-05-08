"""Tests for the SMQL PostgreSQL code generator."""

from smql_compiler.parser import parse_smql
from smql_compiler.codegen import PostgresCodeGenerator


def _compile(source: str, param_values: dict | None = None) -> tuple[str, list]:
    """Helper: parse SMQL source and generate SQL."""
    ast = parse_smql(source)
    gen = PostgresCodeGenerator(param_values=param_values)
    return gen.generate(ast)


# ------------------------------------------------------------------
# Basic pipeline
# ------------------------------------------------------------------

def test_simple_from_take():
    """A minimal pipeline emits SELECT * with FROM and LIMIT."""
    sql, params = _compile("from users\ntake 5\n")
    assert "SELECT *" in sql
    assert "FROM users" in sql
    assert "LIMIT 5" in sql
    assert params == []


def test_default_limit():
    """When no take clause is present, a safety LIMIT 100 is added."""
    sql, _ = _compile("from orders\n")
    assert "LIMIT 100" in sql


# ------------------------------------------------------------------
# Filter → WHERE
# ------------------------------------------------------------------

def test_filter_literal():
    """Filter with a literal integer produces a WHERE clause."""
    sql, params = _compile("from users\nfilter age > 18\ntake 10\n")
    assert "WHERE age > 18" in sql
    assert params == []


def test_multiple_filters_and():
    """Multiple filter clauses are combined with AND."""
    sql, _ = _compile("from users\nfilter age > 18\nfilter active == 1\n")
    assert "WHERE age > 18 AND active = 1" in sql


# ------------------------------------------------------------------
# Parameter handling
# ------------------------------------------------------------------

def test_param_placeholder():
    """ParameterRef nodes become $1, $2, etc."""
    sql, params = _compile(
        "from users\nfilter age > @min_age\nfilter status == @status\n",
        param_values={"min_age": 18, "status": "active"},
    )
    assert "$1" in sql
    assert "$2" in sql
    assert params == [18, "active"]


# ------------------------------------------------------------------
# JOIN
# ------------------------------------------------------------------

def test_inner_join():
    """An inner join is emitted as JOIN … ON."""
    sql, _ = _compile(
        "from users\njoin orders as o on users.id == o.user_id\ntake 10\n"
    )
    assert "JOIN orders AS o ON users.id = o.user_id" in sql


def test_left_join():
    """A left join keeps the LEFT keyword."""
    sql, _ = _compile(
        "from users\nleft join orders as o on users.id == o.user_id\n"
    )
    assert "LEFT JOIN orders AS o ON users.id = o.user_id" in sql


# ------------------------------------------------------------------
# Aggregate → GROUP BY
# ------------------------------------------------------------------

def test_aggregate_group_by():
    """Aggregate clause generates GROUP BY and aggregate SELECT."""
    sql, _ = _compile(
        "from orders\n"
        "aggregate total = sum(amount) by customer_id\n"
    )
    assert "GROUP BY customer_id" in sql
    assert "SUM(amount)" in sql


# ------------------------------------------------------------------
# Sort → ORDER BY
# ------------------------------------------------------------------

def test_sort_desc():
    """Sort clause generates ORDER BY … DESC."""
    sql, _ = _compile("from users\nsort age desc\n")
    assert "ORDER BY" in sql
    assert "DESC" in sql


# ------------------------------------------------------------------
# Select
# ------------------------------------------------------------------

def test_select_columns():
    """Explicit select clause picks the specified columns."""
    sql, _ = _compile("from users\nselect name, email\n")
    assert "SELECT name, email" in sql
    assert "SELECT *" not in sql


def test_select_star_default():
    """Without a select clause, SELECT * is used."""
    sql, _ = _compile("from users\ntake 20\n")
    assert "SELECT *" in sql


# ------------------------------------------------------------------
# Full pipeline (mirrors examples/basic.smql)
# ------------------------------------------------------------------

def test_full_pipeline():
    """Compile the canonical basic.smql pipeline and verify structure."""
    source = (
        "from users\n"
        "filter age > @min_age\n"
        "join orders as o on users.id == o.user_id\n"
        "aggregate total_spent = sum(o.amount) by users.id, users.name\n"
        "sort total_spent desc\n"
        "take 10\n"
        "select name, total_spent\n"
    )
    sql, params = _compile(source, param_values={"min_age": 18})

    assert "FROM users" in sql
    assert "JOIN orders AS o ON users.id = o.user_id" in sql
    assert "WHERE age > $1" in sql
    assert "GROUP BY users.id, users.name" in sql
    assert "ORDER BY" in sql
    assert "DESC" in sql
    assert "LIMIT 10" in sql
    assert "SUM(o.amount) AS total_spent" in sql
    assert params == [18]


# ------------------------------------------------------------------
# Security: string literals must be parameterized
# ------------------------------------------------------------------

def test_string_literal_parameterized():
    """String literals must use $N placeholders, never inline SQL strings."""
    sql, params = _compile(
        'from users\nfilter country == "TR"\ntake 10\n'
    )
    assert "$1" in sql
    assert "TR" not in sql  # Must NOT appear inline in the SQL
    assert params == ["TR"]


def test_string_literal_no_inline_quotes():
    """Ensure no single-quoted string values appear in the SQL output."""
    sql, params = _compile(
        'from users\nfilter status == "active"\n'
    )
    assert "'active'" not in sql
    assert "$1" in sql
    assert params == ["active"]


# ------------------------------------------------------------------
# Security: missing parameter raises ValueError
# ------------------------------------------------------------------

def test_missing_param_raises():
    """Using @name without providing a value must raise ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Missing value for parameter '@min_age'"):
        _compile("from users\nfilter age > @min_age\n")


# ------------------------------------------------------------------
# Literal type preservation
# ------------------------------------------------------------------

def test_int_literal_inline():
    """Integer literals remain inline (no placeholder)."""
    sql, params = _compile("from users\nfilter age > 18\n")
    assert "18" in sql
    assert params == []


def test_float_literal_inline():
    """Float literals remain inline (no placeholder)."""
    sql, params = _compile("from orders\nfilter total > 99.5\n")
    assert "99.5" in sql
    assert params == []


# ------------------------------------------------------------------
# Sort with qualified name (no regex needed)
# ------------------------------------------------------------------

def test_sort_qualified_name():
    """Sort on a qualified name (table.column) works without regex hacks."""
    sql, _ = _compile("from users\nsort users.name desc\n")
    assert "ORDER BY users.name DESC" in sql


def test_sort_simple_name():
    """Sort on a simple column name produces correct ORDER BY."""
    sql, _ = _compile("from users\nsort age asc\n")
    assert "ORDER BY age ASC" in sql


# ------------------------------------------------------------------
# Subqueries and aliases
# ------------------------------------------------------------------

def test_from_alias():
    """From clause with alias generates AS alias."""
    sql, _ = _compile("from users as u\ntake 5\n")
    assert "FROM users AS u" in sql


def test_from_subquery():
    """From clause with subquery pipeline."""
    sql, _ = _compile(
        "from (\n  from users\n  filter age > 18\n) as active_users\n"
    )
    assert "FROM (SELECT *\nFROM users\nWHERE age > 18\nLIMIT 100) AS active_users" in sql


