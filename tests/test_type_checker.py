"""Tests for the SMQL type checker."""

import json
from pathlib import Path

from smql_compiler.parser import parse_smql
from smql_compiler.type_checker import SMQLTypeChecker


def _load_schema() -> dict:
    """Load the test schema from grammar/schema.json."""
    schema_path = Path(__file__).parent.parent / "grammar" / "schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


SCHEMA = _load_schema()


def _check(source: str, schema: dict | None = None) -> SMQLTypeChecker:
    """Parse source, run the type checker, and return the checker."""
    ast = parse_smql(source)
    checker = SMQLTypeChecker(schema=schema)
    checker.check(ast)
    return checker


# ------------------------------------------------------------------
# Valid pipelines
# ------------------------------------------------------------------

def test_valid_table_and_column():
    """Known table + known column passes without errors."""
    checker = _check("from users\nfilter age > 18\n", schema=SCHEMA)
    assert checker.errors == []


def test_valid_qualified_name():
    """Qualified name with known table.column passes."""
    checker = _check(
        "from users\njoin orders as o on users.id == o.user_id\n",
        schema=SCHEMA,
    )
    assert checker.errors == []


def test_no_schema_skips_table_check():
    """Without a schema, table/column checks are skipped."""
    checker = _check("from nonexistent\nfilter foo > 1\n")
    assert checker.errors == []


# ------------------------------------------------------------------
# Unknown table
# ------------------------------------------------------------------

def test_unknown_table():
    """Referencing a table not in the schema produces an error."""
    checker = _check("from customers\nfilter id > 0\n", schema=SCHEMA)
    assert any("Table 'customers' not found" in e for e in checker.errors)


def test_unknown_table_in_join():
    """Unknown table in a JOIN also produces an error."""
    checker = _check(
        "from users\njoin invoices as i on users.id == i.user_id\n",
        schema=SCHEMA,
    )
    assert any("Table 'invoices' not found" in e for e in checker.errors)


# ------------------------------------------------------------------
# Unknown column
# ------------------------------------------------------------------

def test_unknown_column():
    """Referencing a column not in the table produces an error."""
    checker = _check(
        "from users\nfilter users.phone == 1\n",
        schema=SCHEMA,
    )
    assert any("Column 'phone' not found in table 'users'" in e for e in checker.errors)


# ------------------------------------------------------------------
# == null rejection
# ------------------------------------------------------------------

def test_eq_null_rejected():
    """Using == null should produce an error suggesting 'is null'."""
    checker = _check("from users\nfilter name == null\n", schema=SCHEMA)
    assert any("Use 'is null'" in e for e in checker.errors)


def test_is_null_accepted():
    """Using 'is null' should not produce the == null error."""
    checker = _check("from users\nfilter name is null\n", schema=SCHEMA)
    null_errors = [e for e in checker.errors if "is null" in e.lower()]
    assert null_errors == []


# ------------------------------------------------------------------
# Aggregate scope
# ------------------------------------------------------------------

def test_aggregate_scope_violation():
    """After aggregation, using a column not in group_by raises an error."""
    checker = _check(
        "from orders\n"
        "aggregate total = sum(amount) by user_id\n"
        "filter orders.status == 1\n",
        schema=SCHEMA,
    )
    assert any("not available after aggregation" in e for e in checker.errors)


def test_aggregate_scope_valid_group_by():
    """A column that is in group_by is allowed after aggregation."""
    checker = _check(
        "from orders\n"
        "aggregate total = sum(amount) by user_id\n"
        "sort user_id desc\n",
        schema=SCHEMA,
    )
    scope_errors = [e for e in checker.errors if "not available after aggregation" in e]
    assert scope_errors == []


def test_aggregate_scope_valid_metric():
    """A metric name is allowed after aggregation."""
    checker = _check(
        "from orders\n"
        "aggregate total = sum(amount) by user_id\n"
        "sort total desc\n",
        schema=SCHEMA,
    )
    scope_errors = [e for e in checker.errors if "not available after aggregation" in e]
    assert scope_errors == []
