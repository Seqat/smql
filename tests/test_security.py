"""Security-focused tests for the SMQL compiler.

These tests verify that the compiler enforces the security guarantees
documented in the README: parameterization, null-safety, and safe limits.
"""

import pytest
from lark.exceptions import UnexpectedToken, UnexpectedCharacters

from smql_compiler.parser import parse_smql
from smql_compiler.codegen import PostgresCodeGenerator
from smql_compiler.type_checker import SMQLTypeChecker


def _compile(source: str, param_values: dict | None = None) -> tuple[str, list]:
    """Parse SMQL source and generate SQL."""
    ast = parse_smql(source)
    gen = PostgresCodeGenerator(param_values=param_values)
    return gen.generate(ast)


# ------------------------------------------------------------------
# Injection prevention: string literals are never inline
# ------------------------------------------------------------------

def test_string_literal_always_parameterized():
    """String values must always become $N placeholders, not inline SQL."""
    sql, params = _compile('from users\nfilter name == "alice"\n')
    assert "alice" not in sql
    assert "$1" in sql
    assert params == ["alice"]


def test_multiple_string_literals_parameterized():
    """Multiple string literals each get their own placeholder."""
    sql, params = _compile(
        'from users\nfilter name == "alice" and country == "TR"\n'
    )
    assert "alice" not in sql
    assert "TR" not in sql
    assert "$1" in sql
    assert "$2" in sql
    assert params == ["alice", "TR"]


def test_string_with_sql_injection_attempt():
    """A string that looks like SQL injection is safely parameterized."""
    sql, params = _compile(
        "from users\nfilter name == \"'; DROP TABLE users; --\"\n"
    )
    assert "DROP TABLE" not in sql
    assert "$1" in sql
    assert params == ["'; DROP TABLE users; --"]


# ------------------------------------------------------------------
# from @table is syntactically impossible
# ------------------------------------------------------------------

def test_from_at_table_rejected():
    """Attempting `from @variable` must be rejected by the parser."""
    with pytest.raises((UnexpectedToken, UnexpectedCharacters)):
        parse_smql("from @user_table\nfilter id > 0\n")


# ------------------------------------------------------------------
# == null rejection
# ------------------------------------------------------------------

def test_eq_null_rejected_by_type_checker():
    """== null must produce a type-checker error."""
    ast = parse_smql("from users\nfilter name == null\n")
    checker = SMQLTypeChecker()
    checker.check(ast)
    assert any("Use 'is null'" in e for e in checker.errors)


def test_ne_null_rejected_by_type_checker():
    """!= null must also produce a type-checker error."""
    ast = parse_smql("from users\nfilter name != null\n")
    checker = SMQLTypeChecker()
    checker.check(ast)
    assert any("Use 'is null'" in e for e in checker.errors)


def test_is_null_accepted():
    """is null must NOT produce the == null error."""
    ast = parse_smql("from users\nfilter name is null\n")
    checker = SMQLTypeChecker()
    checker.check(ast)
    null_errors = [e for e in checker.errors if "is null" in e]
    assert null_errors == []


def test_is_not_null_accepted():
    """is not null must NOT produce any null-related error."""
    ast = parse_smql("from users\nfilter name is not null\n")
    checker = SMQLTypeChecker()
    checker.check(ast)
    null_errors = [e for e in checker.errors if "null" in e.lower()]
    assert null_errors == []


# ------------------------------------------------------------------
# Default LIMIT enforcement
# ------------------------------------------------------------------

def test_default_limit_enforced():
    """Without an explicit take, a safety LIMIT 100 is always present."""
    sql, _ = _compile("from users\n")
    assert "LIMIT 100" in sql


def test_explicit_take_overrides_default():
    """An explicit take overrides the default limit."""
    sql, _ = _compile("from users\ntake 50\n")
    assert "LIMIT 50" in sql
    assert "LIMIT 100" not in sql


def test_take_zero():
    """take 0 should produce LIMIT 0."""
    sql, _ = _compile("from users\ntake 0\n")
    assert "LIMIT 0" in sql


# ------------------------------------------------------------------
# Missing parameter raises error
# ------------------------------------------------------------------

def test_missing_param_raises_value_error():
    """Using @name without providing a value raises ValueError."""
    with pytest.raises(ValueError, match="Missing value for parameter '@min_age'"):
        _compile("from users\nfilter age > @min_age\n")


def test_missing_one_of_many_params():
    """When only some params are provided, the missing one raises."""
    with pytest.raises(ValueError, match="Missing value for parameter '@status'"):
        _compile(
            "from users\nfilter age > @min_age and status == @status\n",
            param_values={"min_age": 18},
        )
