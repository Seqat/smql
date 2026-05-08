"""Tests for WHERE vs HAVING placement in the SMQL code generator."""

from smql_compiler.parser import parse_smql
from smql_compiler.codegen import PostgresCodeGenerator


def _compile(source: str, param_values: dict | None = None) -> tuple[str, list]:
    """Helper: parse SMQL source and generate SQL."""
    ast = parse_smql(source)
    gen = PostgresCodeGenerator(param_values=param_values)
    return gen.generate(ast)


# ------------------------------------------------------------------
# Filter BEFORE aggregate → WHERE
# ------------------------------------------------------------------

def test_filter_before_aggregate_goes_to_where():
    """A filter that appears before an aggregate should emit WHERE."""
    sql, _ = _compile(
        "from orders\n"
        "filter amount > 0\n"
        "aggregate total = sum(amount) by customer_id\n"
    )
    assert "WHERE amount > 0" in sql
    assert "HAVING" not in sql
    assert "GROUP BY customer_id" in sql


# ------------------------------------------------------------------
# Filter AFTER aggregate → HAVING
# ------------------------------------------------------------------

def test_filter_after_aggregate_goes_to_having():
    """A filter that appears after an aggregate should emit HAVING."""
    sql, _ = _compile(
        "from orders\n"
        "aggregate total = sum(amount) by customer_id\n"
        "filter total > 1000\n"
    )
    assert "HAVING total > 1000" in sql
    assert "WHERE" not in sql
    assert "GROUP BY customer_id" in sql


def test_filter_before_and_after_aggregate():
    """Filters on both sides of aggregate produce WHERE and HAVING."""
    sql, _ = _compile(
        "from orders\n"
        "filter amount > 0\n"
        "aggregate total = sum(amount) by customer_id\n"
        "filter total > 500\n"
    )
    assert "WHERE amount > 0" in sql
    assert "HAVING total > 500" in sql
    assert "GROUP BY customer_id" in sql


def test_multiple_having_conditions():
    """Multiple post-aggregate filters are combined with AND in HAVING."""
    sql, _ = _compile(
        "from orders\n"
        "aggregate total = sum(amount), cnt = count(id) by customer_id\n"
        "filter total > 100\n"
        "filter cnt > 2\n"
    )
    assert "HAVING total > 100 AND cnt > 2" in sql
    assert "WHERE" not in sql
