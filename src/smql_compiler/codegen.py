"""SQL code generator for SMQL AST. Target: PostgreSQL."""

from .ast import Program


class PostgresCodeGenerator:
    """Generates parameterized PostgreSQL SQL from a SMQL AST."""

    def __init__(self):
        self.params = []
        self.param_counter = 0

    def generate(self, program: Program) -> tuple[str, list]:
        """Generate SQL string and bound parameters list."""
        # TODO: Walk the AST and produce SQL
        sql = "-- SMQL compiled SQL placeholder"
        params = []
        return sql, params

    def _next_param(self, value) -> str:
        """Register a parameter and return $N placeholder."""
        self.param_counter += 1
        self.params.append(value)
        return f"${self.param_counter}"
