"""Type checker for SMQL AST."""

from .ast import (
    Program, QueryDefinition, Node,
    FromClause, FilterClause, JoinClause, AggregateClause,
    SortClause, TakeClause, SelectClause, DeriveClause,
    BinaryOp, UnaryOp, Literal, ParameterRef, QualifiedName,
    FunctionCall, Expression,
)


class SMQLTypeChecker:
    """Validates types, scopes, and security policies on the AST.

    Accepts an optional *schema* dictionary that describes the known
    tables, columns, and enums.  When no schema is provided the checker
    skips table/column resolution but still enforces syntactic rules
    (e.g. ``== null`` rejection, aggregate-scope checks).
    """

    def __init__(self, schema: dict | None = None):
        self.schema: dict = schema or {}
        self.errors: list[str] = []
        self.warnings: list[str] = []

        # Resolved table info: table_name -> {col_name: col_type, ...}
        self._tables: dict[str, dict[str, str]] = {}
        # Known enum types: enum_name -> list of allowed values
        self._enums: dict[str, list[str]] = {}
        # Alias → real table name
        self._aliases: dict[str, str] = {}
        # Columns available in the current scope (after aggregation these
        # are restricted to group_by + aggregate metric names).
        self._in_aggregate_scope: bool = False
        self._group_by_names: set[str] = set()
        self._metric_names: set[str] = set()

        if self.schema:
            for tname, tinfo in self.schema.get("tables", {}).items():
                self._tables[tname] = tinfo.get("columns", {})
            for ename, evalues in self.schema.get("enums", {}).items():
                self._enums[ename] = evalues

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, program: Program) -> bool:
        """Run all type checks. Returns True if no errors."""
        self.errors = []
        self.warnings = []
        self._aliases = {}
        self._in_aggregate_scope = False
        self._group_by_names = set()
        self._metric_names = set()

        # Collect pipeline steps (top-level or first QueryDefinition)
        pipeline: list[Node] = []
        for stmt in program.statements:
            if isinstance(stmt, QueryDefinition):
                pipeline = stmt.pipeline
                break
            elif isinstance(stmt, Node):
                pipeline.append(stmt)

        self._check_pipeline(pipeline)
        return len(self.errors) == 0

    def get_diagnostics(self) -> list[str]:
        """Return human-readable diagnostic messages."""
        return self.errors + self.warnings

    # ------------------------------------------------------------------
    # Pipeline walker
    # ------------------------------------------------------------------

    def _check_pipeline(self, steps: list[Node]) -> None:
        for step in steps:
            if isinstance(step, FromClause):
                self._check_from(step)

            elif isinstance(step, JoinClause):
                self._check_join(step)

            elif isinstance(step, FilterClause):
                if step.expression is not None:
                    self._check_expr(step.expression)

            elif isinstance(step, AggregateClause):
                self._enter_aggregate_scope(step)

            elif isinstance(step, SortClause):
                if step.field is not None:
                    self._check_expr(step.field)

            elif isinstance(step, SelectClause):
                self._check_select(step)

            elif isinstance(step, DeriveClause):
                if step.expression is not None:
                    self._check_expr(step.expression)

    # ------------------------------------------------------------------
    # Clause-level checks
    # ------------------------------------------------------------------

    def _check_from(self, node: FromClause) -> None:
        table = node.source
        if self._tables and table not in self._tables:
            self.errors.append(f"Table '{table}' not found")
        if node.alias:
            self._aliases[node.alias] = table

    def _check_join(self, node: JoinClause) -> None:
        table = node.source
        if self._tables and table not in self._tables:
            self.errors.append(f"Table '{table}' not found")
        if node.alias:
            self._aliases[node.alias] = table
        if node.condition is not None:
            self._check_expr(node.condition)

    def _enter_aggregate_scope(self, node: AggregateClause) -> None:
        """Record group-by columns and metric names, then enter
        restricted scope mode."""
        self._group_by_names = set()
        self._metric_names = set()

        # Check aggregate expressions *before* entering restricted
        # scope — these references are still valid at this point.
        for g in node.group_by:
            self._check_expr(g)
            full_name = self._expr_name(g)
            self._group_by_names.add(full_name)
            # Also allow the short (last-part) form so that
            # ``select name`` works when group_by has ``users.name``.
            if isinstance(g, QualifiedName) and len(g.parts) > 1:
                self._group_by_names.add(g.parts[-1])

        for m in node.metrics:
            self._metric_names.add(m["name"])
            if isinstance(m.get("expr"), Expression):
                self._check_expr(m["expr"])

        # Now enter restricted scope for subsequent pipeline steps.
        self._in_aggregate_scope = True

    def _check_select(self, node: SelectClause) -> None:
        for item in node.fields:
            if isinstance(item, dict):
                expr = item.get("expr")
                if isinstance(expr, Expression):
                    self._check_expr(expr)
            elif isinstance(item, Expression):
                self._check_expr(item)

    # ------------------------------------------------------------------
    # Expression-level checks
    # ------------------------------------------------------------------

    def _check_expr(self, expr: Expression) -> None:
        if expr is None:
            return

        if isinstance(expr, BinaryOp):
            self._check_null_comparison(expr)
            self._check_expr(expr.left)
            self._check_expr(expr.right)
            return

        if isinstance(expr, UnaryOp):
            self._check_expr(expr.expression)
            return

        if isinstance(expr, QualifiedName):
            self._check_qualified_name(expr)
            return

        if isinstance(expr, FunctionCall):
            for arg in expr.arguments:
                self._check_expr(arg)
            return

        # Literal, ParameterRef – nothing to check at this level.

    def _check_null_comparison(self, expr: BinaryOp) -> None:
        """Reject ``== null`` / ``!= null``.  Users must write
        ``is null`` / ``is not null`` instead."""
        if expr.operator in ("==", "!="):
            if self._is_null_literal(expr.right) or self._is_null_literal(expr.left):
                self.errors.append("Use 'is null' instead of '== null'")

    def _check_qualified_name(self, expr: QualifiedName) -> None:
        parts = expr.parts
        if len(parts) == 2:
            table_ref, col = parts

            # Check if this is an enum reference (e.g. user_status.active)
            if table_ref in self._enums:
                if col not in self._enums[table_ref]:
                    self.errors.append(
                        f"Value '{col}' not in enum '{table_ref}'"
                    )
                return  # enum refs are not table.column lookups

            # Resolve alias → real table name
            real_table = self._aliases.get(table_ref, table_ref)
            if self._tables:
                if real_table not in self._tables:
                    self.errors.append(f"Table '{table_ref}' not found")
                elif col not in self._tables[real_table]:
                    self.errors.append(
                        f"Column '{col}' not found in table '{real_table}'"
                    )

        # Aggregate scope check — the name (simple or qualified) must be
        # one of the group_by columns or a metric name.
        if self._in_aggregate_scope:
            name = self._expr_name(expr)
            if name not in self._group_by_names and name not in self._metric_names:
                self.errors.append(
                    f"Column '{name}' not available after aggregation"
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_null_literal(expr) -> bool:
        """Return True for Literal(None) or QualifiedName(['null']).

        The parser represents bare ``null`` as a QualifiedName since
        there is no dedicated null token in the grammar."""
        if isinstance(expr, Literal) and expr.value is None:
            return True
        if isinstance(expr, QualifiedName) and expr.parts == ["null"]:
            return True
        return False

    @staticmethod
    def _expr_name(expr) -> str:
        """Return a canonical string name for an expression, used for
        aggregate scope tracking."""
        if isinstance(expr, QualifiedName):
            return ".".join(expr.parts)
        return str(expr)
