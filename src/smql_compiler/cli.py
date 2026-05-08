"""SMQL CLI – command-line interface for the compiler."""

import typer
from pathlib import Path
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from .parser import parse_file
from .type_checker import SMQLTypeChecker
from .codegen import PostgresCodeGenerator

app = typer.Typer(
    name="smql",
    help="SMQL Compiler – compile .smql files to safe parameterized SQL",
)
console = Console()


@app.command()
def compile(
    path: str = typer.Argument(..., help="Path to .smql file"),
    target: str = typer.Option("postgres", "--target", "-t", help="Target SQL dialect"),
    output: str = typer.Option(None, "--output", "-o", help="Output file (prints to stdout if omitted)"),
    explain: bool = typer.Option(False, "--explain", "-e", help="Print source map and diagnostics"),
    param: list[str] = typer.Option(None, "--param", "-p", help="Parameter key=value pairs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Output SQL with placeholders without requiring actual parameter values"),
):
    """Compile a SMQL file to SQL."""
    file_path = Path(path)

    if not file_path.exists():
        console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(code=1)

    if file_path.suffix != ".smql":
        console.print(f"[yellow]Warning:[/yellow] Expected .smql extension, got {file_path.suffix}")

    def _parse_val(v: str):
        if v.isdigit() or (v.startswith('-') and v[1:].isdigit()):
            return int(v)
        try:
            return float(v)
        except ValueError:
            return v

    param_values = {}
    if param:
        for p in param:
            if "=" in p:
                k, v = p.split("=", 1)
                param_values[k] = _parse_val(v)
            else:
                param_values[p] = ""

    class DryRunDict(dict):
        def __contains__(self, key):
            return True
        def __getitem__(self, key):
            return f"@{key}"
        def __bool__(self):
            return True

    if dry_run:
        param_values = DryRunDict()

    try:
        # Parse
        ast = parse_file(str(file_path))

        # Load schema (if available)
        schema: dict | None = None
        schema_path = Path(__file__).parent.parent.parent / "grammar" / "schema.json"
        if schema_path.exists():
            import json
            schema = json.loads(schema_path.read_text(encoding="utf-8"))

        # Type check
        checker = SMQLTypeChecker(schema=schema)
        is_valid = checker.check(ast)

        if explain:
            for diag in checker.get_diagnostics():
                console.print(diag)

        if not is_valid:
            for err in checker.errors:
                console.print(f"[red]Error:[/red] {err}")
            console.print("[red]Type checking failed.[/red]")
            raise typer.Exit(code=1)

        # Generate SQL
        generator = PostgresCodeGenerator(param_values=param_values)
        sql, params = generator.generate(ast)

        # Output
        if output:
            Path(output).write_text(sql, encoding='utf-8')
            console.print(f"[green]✓[/green] Compiled to {output}")
        else:
            syntax = Syntax(sql, "sql", theme="monokai", line_numbers=True)
            console.print(syntax)

            if params:
                param_table = Table("Index", "Value")
                for i, val in enumerate(params, 1):
                    param_table.add_row(f"${i}", repr(val))
                console.print(param_table)

    except ValueError as e:
        console.print(f"[red]Parameter Error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Compilation failed:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Print SMQL compiler version."""
    from . import __version__
    console.print(f"SMQL Compiler v{__version__}")


if __name__ == "__main__":
    app()
