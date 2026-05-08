"""AST node definitions for SMQL."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Node:
    """Base AST node."""
    line: int = 0
    column: int = 0


@dataclass
class Program(Node):
    """Root node: a list of top-level statements."""
    statements: list['Node'] = field(default_factory=list)


@dataclass
class ImportStatement(Node):
    """import 'path/to/file.smql'"""
    path: str = ""


@dataclass
class Parameter(Node):
    """@param_name: type"""
    name: str = ""
    type_annotation: str = ""


@dataclass
class QueryDefinition(Node):
    """query name(@params) returns { fields } pipeline end"""
    name: str = ""
    params: list['Parameter'] = field(default_factory=list)
    return_fields: list[dict] = field(default_factory=list)
    pipeline: list['Node'] = field(default_factory=list)


@dataclass
class FromClause(Node):
    """from source"""
    source: str = ""
    alias: Optional[str] = None


@dataclass
class FromSubquery(Node):
    """from ( pipeline )"""
    pipeline: list['Node'] = field(default_factory=list)


@dataclass
class FilterClause(Node):
    """filter expression"""
    expression: Optional['Expression'] = None


@dataclass
class DeriveClause(Node):
    """derive name = expression"""
    name: str = ""
    expression: Optional['Expression'] = None


@dataclass
class JoinClause(Node):
    """[join_type] join source on expression"""
    join_type: str = "inner"  # 'inner', 'left', 'right', 'cross'
    source: str = ""
    alias: Optional[str] = None
    condition: Optional['Expression'] = None


@dataclass
class AggregateClause(Node):
    """aggregate metrics by group_fields"""
    metrics: list[dict] = field(default_factory=list)
    group_by: list['Expression'] = field(default_factory=list)


@dataclass
class SortClause(Node):
    """sort field [asc|desc]"""
    field: Optional['Expression'] = None
    direction: str = 'asc'


@dataclass
class TakeClause(Node):
    """take N"""
    count: int = 0


@dataclass
class SelectClause(Node):
    """select fields"""
    fields: list[dict] = field(default_factory=list)


@dataclass
class UnionClause(Node):
    """| union ( pipeline )"""
    pipeline: list['Node'] = field(default_factory=list)


# --- Expression AST nodes ---

@dataclass
class Expression(Node):
    """Base expression."""
    pass


@dataclass
class BinaryOp(Expression):
    """left op right"""
    left: Optional['Expression'] = None
    operator: str = ""
    right: Optional['Expression'] = None


@dataclass
class UnaryOp(Expression):
    """op expression"""
    operator: str = ""
    expression: Optional['Expression'] = None


@dataclass
class Literal(Expression):
    """Scalar literal value."""
    value: object = None


@dataclass
class ParameterRef(Expression):
    """@param_name"""
    name: str = ""


@dataclass
class QualifiedName(Expression):
    """table.column or enum_type.value"""
    parts: list[str] = field(default_factory=list)


@dataclass
class FunctionCall(Expression):
    """function_name(args)"""
    name: str = ""
    arguments: list['Expression'] = field(default_factory=list)
