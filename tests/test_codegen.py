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
    assert "JOIN orders o ON users.id = o.user_id" in sql


def test_left_join():
    """A left join keeps the LEFT keyword."""
    sql, _ = _compile(
        "from users\nleft join orders as o on users.id == o.user_id\n"
    )
    assert "LEFT JOIN orders o ON users.id = o.user_id" in sql


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
    assert "JOIN orders o ON users.id = o.user_id" in sql
    assert "WHERE age > $1" in sql
    assert "GROUP BY users.id, users.name" in sql
    assert "ORDER BY" in sql
    assert "DESC" in sql
    assert "LIMIT 10" in sql
    assert "SUM(o.amount) AS total_spent" in sql
    assert params == [18]
