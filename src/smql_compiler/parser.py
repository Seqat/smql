"""SMQL Parser using Lark."""

from pathlib import Path
from lark import Lark, Tree, Token, Transformer, v_args
from .ast import *


class SMQLTransformer(Transformer):
    """Converts Lark parse tree into SMQL AST nodes."""

    def start(self, items):
        # Filter out None items (from _NL)
        stmts = [i for i in items if i is not None]
        return Program(statements=stmts)

    def import_stmt(self, items):
        path_token = items[0]
        return ImportStatement(path=str(path_token).strip('"'))

    def query_def(self, items):
        name = str(items[0])
        params = []
        steps = []
        for item in items[1:]:
            if isinstance(item, list):
                params = item
            elif isinstance(item, Node):
                steps.append(item)
        return QueryDefinition(name=name, params=params, pipeline=steps)

    def param_list(self, items):
        return list(items)

    def param(self, items):
        return Parameter(name=str(items[0]), type_annotation=str(items[1]))

    def return_clause(self, items):
        return items[0]

    def field_list(self, items):
        return list(items)

    def field(self, items):
        return {"name": str(items[0]), "type": str(items[1])}

    def type_annotation(self, items):
        return items[0]

    def type_name(self, items):
        return " ".join(str(i) for i in items)

    # --- Step clauses ---

    def from_clause(self, items):
        source = items[0]
        if isinstance(source, str):
            return FromClause(source=source)
        return FromClause(source=str(source))

    def filter_clause(self, items):
        return FilterClause(expression=items[0])

    def derive_clause(self, items):
        return DeriveClause(name=str(items[0]), expression=items[1])

    def join_clause(self, items):
        join_type = "inner"
        source = ""
        alias = None
        condition = None
        for item in items:
            if isinstance(item, Tree) and item.data == "join_type":
                join_type = str(item.children[0])
            elif isinstance(item, Token) and item.type == "JOIN_TYPE":
                join_type = str(item)
            elif isinstance(item, Expression):
                condition = item
            elif isinstance(item, Token) and item.type == "CNAME":
                if not source:
                    source = str(item)
                else:
                    alias = str(item)
            elif isinstance(item, str) and not source:
                source = item
        return JoinClause(join_type=join_type, source=source, alias=alias, condition=condition)

    def aggregate_clause(self, items):
        metrics = items[0] if isinstance(items[0], list) else []
        group_by = items[1] if len(items) > 1 else []
        return AggregateClause(metrics=metrics, group_by=group_by)

    def aggregate_list(self, items):
        return list(items)

    def aggregate_item(self, items):
        # items: [CNAME, AGG_FN, expression]
        return {"name": str(items[0]), "fn": str(items[1]), "expr": items[2]}

    def group_list(self, items):
        return list(items)

    def sort_clause(self, items):
        sort_items = items[0] if isinstance(items[0], list) else items
        # For simplicity, take the first sort item
        if sort_items:
            first = sort_items[0] if isinstance(sort_items, list) else sort_items
            if isinstance(first, dict):
                return SortClause(field=str(first.get("expr", "")), direction=first.get("dir", "asc"))
        return SortClause()

    def sort_list(self, items):
        return list(items)

    def sort_item(self, items):
        expr = items[0]
        direction = str(items[1]) if len(items) > 1 else "asc"
        return {"expr": expr, "dir": direction}

    def take_clause(self, items):
        return TakeClause(count=int(str(items[0])))

    def select_clause(self, items):
        fields = items[0] if isinstance(items[0], list) else list(items)
        return SelectClause(fields=fields)

    def select_list(self, items):
        return list(items)

    def select_item(self, items):
        expr = items[0]
        alias = str(items[1]) if len(items) > 1 else None
        return {"expr": expr, "alias": alias}

    def union_clause(self, items):
        return UnionClause(pipeline=list(items))

    def source(self, items):
        return str(items[0])

    def call_args(self, items):
        return list(items)

    def call_arg(self, items):
        return items

    # --- Expressions ---

    def comparison(self, items):
        left, op, right = items[0], str(items[1]), items[2]
        return BinaryOp(left=left, operator=op, right=right)

    def is_null(self, items):
        return UnaryOp(operator="is null", expression=items[0])

    def is_not_null(self, items):
        return UnaryOp(operator="is not null", expression=items[0])

    def add(self, items):
        return BinaryOp(left=items[0], operator="+", right=items[1])

    def sub(self, items):
        return BinaryOp(left=items[0], operator="-", right=items[1])

    def mul(self, items):
        return BinaryOp(left=items[0], operator="*", right=items[1])

    def div(self, items):
        return BinaryOp(left=items[0], operator="/", right=items[1])

    def not_expr(self, items):
        return UnaryOp(operator="not", expression=items[0])

    def int_literal(self, items):
        return Literal(value=int(str(items[0])))

    def float_literal(self, items):
        return Literal(value=float(str(items[0])))

    def string_literal(self, items):
        return Literal(value=str(items[0]).strip('"'))

    def param_ref(self, items):
        return ParameterRef(name=str(items[0]))

    def qualified_name(self, items):
        return QualifiedName(parts=[str(i) for i in items])

    def name(self, items):
        return QualifiedName(parts=[str(items[0])])

    def function_call(self, items):
        name = str(items[0])
        args = items[1] if len(items) > 1 and isinstance(items[1], list) else []
        return FunctionCall(name=name, arguments=args)

    def arg_list(self, items):
        return list(items)

    def and_expr(self, items):
        return BinaryOp(left=items[0], operator="and", right=items[1])

    def or_expr(self, items):
        return BinaryOp(left=items[0], operator="or", right=items[1])


def get_parser():
    """Load and return a Lark parser for SMQL."""
    grammar_path = Path(__file__).parent.parent.parent / "grammar" / "smql.lark"

    if not grammar_path.exists():
        raise FileNotFoundError(f"Grammar file not found: {grammar_path}")

    grammar_text = grammar_path.read_text(encoding='utf-8')

    parser = Lark(
        grammar_text,
        parser='lalr',
        propagate_positions=True,
    )

    return parser


_transformer = SMQLTransformer()


def parse_smql(source: str) -> Program:
    """Parse a SMQL source string and return an AST."""
    parser = get_parser()
    tree = parser.parse(source)
    return _transformer.transform(tree)


def parse_file(path: str) -> Program:
    """Parse a .smql file and return an AST."""
    source = Path(path).read_text(encoding='utf-8')
    return parse_smql(source)
