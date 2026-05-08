"""Type checker for SMQL AST."""

from .ast import Program, Node


class SMQLTypeChecker:
    """Validates types, scopes, and security policies on the AST."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def check(self, program: Program) -> bool:
        """Run all type checks. Returns True if no errors."""
        self.errors = []
        self.warnings = []
        # TODO: Implement type checking passes
        return len(self.errors) == 0

    def get_diagnostics(self) -> list[str]:
        """Return human-readable diagnostic messages."""
        return self.errors + self.warnings
