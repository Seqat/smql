"""SQL code generator for SMQL AST. Target: PostgreSQL."""


from .ast import (
    Program, QueryDefinition,
    FromClause, FilterClause, JoinClause, AggregateClause,
    SortClause, TakeClause, SelectClause, DeriveClause,
    BinaryOp, UnaryOp, Literal, ParameterRef, QualifiedName,
    FunctionCall, Expression, Node,
)

# Map SMQL comparison operators to SQL operators
_OP_MAP = {
    "==": "=",
    "!=": "<>",
    ">=": ">=",
    "<=": "<=",
    ">": ">",
    "<": "<",
    "and": "AND",
    "or": "OR",
    "+": "+",
    "-": "-",
    "*": "*",
    "/": "/",
}

# Default safety limit when no TakeClause is specified
_DEFAULT_LIMIT = 100


class PostgresCodeGenerator:
    """Generates parameterized PostgreSQL SQL from a SMQL AST."""

    def __init__(self, param_values: dict | None = None):
        self.params: list = []
        self.param_counter: int = 0
        self.param_values: dict = param_values or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, program: Program) -> tuple[str, list]:
        """Generate SQL string and bound parameters list.

        A Program may contain bare pipeline steps (top-level) and/or
        named ``QueryDefinition`` nodes.  For a bare pipeline we emit a
        single SQL statement.  For a ``QueryDefinition`` we compile the
        pipeline inside it.
        """
        self.params = []
        self.param_counter = 0

        # Collect all pipeline steps – either top-level or inside the
        # first QueryDefinition we encounter.
        pipeline: list[Node] = []
        for stmt in program.statements:
            if isinstance(stmt, QueryDefinition):
                pipeline = stmt.pipeline
                break
            elif isinstance(stmt, Node):
                pipeline.append(stmt)

        if not pipeline:
            return "-- empty SMQL pipeline", []

        sql = self._compile_pipeline(pipeline)
        return sql, self.params

    # ------------------------------------------------------------------
    # Pipeline → SQL
    # ------------------------------------------------------------------

    def _compile_pipeline(self, steps: list[Node]) -> str:
        """Walk the list of pipeline steps and assemble a SQL statement."""

        from_parts: list[str] = []
        join_parts: list[str] = []
        where_parts: list[str] = []
        having_parts: list[str] = []
        group_by_parts: list[str] = []
        select_parts: list[str] = []
        order_parts: list[str] = []
        limit_val: int | None = None
        aggregate_metrics: list[dict] = []
        derive_parts: list[tuple[str, str]] = []
        seen_aggregate: bool = False

        for step in steps:
            if isinstance(step, FromClause):
                alias = f" {step.alias}" if step.alias else ""
                from_parts.append(f"{step.source}{alias}")

            elif isinstance(step, JoinClause):
                jtype = step.join_type.upper()
                if jtype == "INNER":
                    jtype = ""          # plain JOIN is INNER by default
                else:
                    jtype = f"{jtype} "
                alias = f" {step.alias}" if step.alias else ""
                cond = self._emit_expr(step.condition) if step.condition else "TRUE"
                join_parts.append(f"{jtype}JOIN {step.source}{alias} ON {cond}")

            elif isinstance(step, FilterClause):
                if step.expression is not None:
                    if seen_aggregate:
                        having_parts.append(self._emit_expr(step.expression))
                    else:
                        where_parts.append(self._emit_expr(step.expression))

            elif isinstance(step, AggregateClause):
                seen_aggregate = True
                aggregate_metrics = step.metrics
                group_by_parts = [self._emit_expr(g) for g in step.group_by]

            elif isinstance(step, SortClause):
                direction = step.direction.upper() if step.direction else "ASC"
                field_sql = self._emit_expr(step.field)
                order_parts.append(f"{field_sql} {direction}")

            elif isinstance(step, TakeClause):
                limit_val = step.count

            elif isinstance(step, SelectClause):
                for item in step.fields:
                    if isinstance(item, dict):
                        expr = item.get("expr")
                        alias = item.get("alias")
                        # The parser may store the string "None" instead of Python None
                        if alias == "None" or alias is None:
                            alias = None
                        expr_sql = self._emit_expr(expr) if isinstance(expr, Expression) else str(expr)
                        if alias:
                            select_parts.append(f"{expr_sql} AS {alias}")
                        else:
                            select_parts.append(expr_sql)
                    elif isinstance(item, Expression):
                        select_parts.append(self._emit_expr(item))
                    else:
                        select_parts.append(str(item))

            elif isinstance(step, DeriveClause):
                expr_sql = self._emit_expr(step.expression) if step.expression else "NULL"
                derive_parts.append((step.name, expr_sql))

        # ---- Build the SELECT list ----
        final_select_parts: list[str] = []

        if select_parts:
            # Resolve select names against aggregate metrics so that
            # e.g. ``select name, total_spent`` picks up the aggregate
            # function expression for ``total_spent``.
            metric_map: dict[str, str] = {}
            for m in aggregate_metrics:
                metric_map[m["name"]] = self._emit_aggregate_expr(m)

            for sp in select_parts:
                if sp in metric_map:
                    final_select_parts.append(f"{metric_map[sp]} AS {sp}")
                else:
                    final_select_parts.append(sp)
        elif aggregate_metrics:
            # No explicit select → include group_by fields + metrics
            final_select_parts.extend(group_by_parts)
            for m in aggregate_metrics:
                final_select_parts.append(
                    f"{self._emit_aggregate_expr(m)} AS {m['name']}"
                )
        else:
            final_select_parts.append("*")

        # Incorporate derives as extra selected expressions when no
        # explicit select is given but derives exist.
        if derive_parts and not select_parts:
            if final_select_parts == ["*"]:
                final_select_parts = ["*"]
            for name, expr_sql in derive_parts:
                final_select_parts.append(f"{expr_sql} AS {name}")

        # ---- Assemble ----
        lines: list[str] = []
        lines.append(f"SELECT {', '.join(final_select_parts)}")

        if from_parts:
            lines.append(f"FROM {', '.join(from_parts)}")

        for jp in join_parts:
            lines.append(jp)

        if where_parts:
            lines.append(f"WHERE {' AND '.join(where_parts)}")

        if group_by_parts:
            lines.append(f"GROUP BY {', '.join(group_by_parts)}")

        if having_parts:
            lines.append(f"HAVING {' AND '.join(having_parts)}")

        if order_parts:
            lines.append(f"ORDER BY {', '.join(order_parts)}")

        # Safety default: always include a LIMIT
        if limit_val is not None:
            lines.append(f"LIMIT {limit_val}")
        else:
            lines.append(f"LIMIT {_DEFAULT_LIMIT}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Expression emitter
    # ------------------------------------------------------------------

    def _emit_expr(self, expr) -> str:
        """Recursively translate an expression AST node to SQL text."""

        if expr is None:
            return "NULL"

        if isinstance(expr, BinaryOp):
            left = self._emit_expr(expr.left)
            right = self._emit_expr(expr.right)
            op = _OP_MAP.get(expr.operator, expr.operator)
            return f"{left} {op} {right}"

        if isinstance(expr, UnaryOp):
            inner = self._emit_expr(expr.expression)
            op = expr.operator.upper()
            if op in ("IS NULL", "IS NOT NULL"):
                return f"{inner} {op}"
            if op == "NOT":
                return f"NOT {inner}"
            return f"{op} {inner}"

        if isinstance(expr, Literal):
            val = expr.value
            if isinstance(val, bool):
                return "TRUE" if val else "FALSE"
            if isinstance(val, str):
                # Security: never interpolate strings into SQL.
                # Always emit a $N placeholder and record the value.
                return self._next_param(val)
            return str(val)

        if isinstance(expr, ParameterRef):
            name = expr.name
            if name not in self.param_values:
                raise ValueError(
                    f"Missing value for parameter '@{name}'"
                )
            value = self.param_values[name]
            return self._next_param(value)

        if isinstance(expr, QualifiedName):
            return ".".join(expr.parts)

        if isinstance(expr, FunctionCall):
            args = ", ".join(self._emit_expr(a) for a in expr.arguments)
            return f"{expr.name.upper()}({args})"

        # Fallback for bare strings (e.g. from sort_item)
        if isinstance(expr, str):
            return expr

        return str(expr)

    def _emit_aggregate_expr(self, metric: dict) -> str:
        """Emit the aggregate function expression for a metric dict."""
        fn = metric["fn"].upper()
        inner = self._emit_expr(metric["expr"])
        return f"{fn}({inner})"


    # ------------------------------------------------------------------
    # Parameter handling
    # ------------------------------------------------------------------

    def _next_param(self, value) -> str:
        """Register a parameter and return $N placeholder."""
        self.param_counter += 1
        self.params.append(value)
        return f"${self.param_counter}"
