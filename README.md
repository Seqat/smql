# SMQL v0.2.0

## SMQL — SeMantic Query Language

A secure, typed, and AI‑friendly query language that compiles to parameterized SQL.
SMQL is not a replacement for SQL; it is a **safe abstraction layer** on top of it.

---

## 🧭 Philosophy

SMQL was designed to solve three core problems in the age of AI‑assisted development:

1. **Security beyond injection** – a policy‑aware, permission‑aware, schema‑aware security model that makes unsafe query construction unrepresentable.
2. **Human readability** – a pipeline‑style syntax that flows left‑to‑right, telling a story step‑by‑step.
3. **AI friendliness** – rich type and enum information that reduces LLM hallucinations, with error messages that help both humans and machines fix mistakes.

---

## ✅ Currently Implemented

| Feature | Status | Notes |
|---|---|---|
| Pipeline parsing | ✅ | `from`, `filter`, `join`, `aggregate`, `sort`, `take`, `select` |
| PostgreSQL code generation | ✅ | Parameterized `$N` placeholders, no string interpolation |
| Parameter binding | ✅ | `@param_name` → `$N` with values passed via `--param` |
| Default safety LIMIT | ✅ | `LIMIT 100` when no `take` is specified |
| Null safety | ✅ | `== null` is rejected; must use `is null` / `is not null` |
| Schema validation | ✅ | Type checker validates tables and columns against `grammar/schema.json` |
| HAVING support | ✅ | `filter` before `aggregate` → `WHERE`; after → `HAVING` |
| Aggregate scope checking | ✅ | Post‑aggregate columns restricted to `group_by` + metrics |
| String literal parameterization | ✅ | String values always emitted as `$N`, never inline |
| Table aliases | ✅ | `from users as u`, `join orders as o on ...` |
| Subquery pipelines | ✅ | `from ( from users filter ... )` compiled as `FROM (SELECT ...)` |
| Query definitions | ✅ | `query name(@params) returns { ... } ... end` |
| CLI | ✅ | `smql compile`, `--param`, `--dry-run`, `--explain`, `--output` |

---

## 🔲 Planned / In Progress

| Feature | Status | Notes |
|---|---|---|
| Window functions | 🔲 | `over`, `partition by`, `row_number()` |
| Recursive queries | 🔲 | `recursive query` |
| DML support | 🔲 | `insert`, `update`, `delete` |
| Multi‑dialect SQL generation | 🔲 | MySQL, SQLite, DuckDB |
| Sensitive column protection | 🔲 | `sensitive`, `pii`, `secret` markers with compile‑time enforcement |
| Policy layer | 🔲 | Row‑level security, tenant isolation |
| VS Code extension with LSP | 🔲 | Autocomplete, live errors |
| AI integration library | 🔲 | LangChain, LlamaIndex connectors |

---

## 🔒 Security at the Core

SMQL is **"secure by design"**:

- **AST‑first:** Queries are never built with string concatenation. Input is parsed into an immutable AST before execution.
- **Parameter isolation:** `@user_input` is attached as a value leaf in the AST, never as code.
- **Symbol / value separation:** Table and column names are symbols, not strings. `from @user_table` is syntactically impossible.
- **Enum locking:** Status fields are compared against compile‑time enums (`user_status.active`), not arbitrary strings.
- **Null safety:** `== null` is invalid; you must write `is null` / `is not null`.
- **Cost limiting:** A `take` clause is mandatory (or a system‑wide `max_rows` policy applies; defaults to `LIMIT 100`).
- **Transpiler safety:** Generated SQL is 100% parameterized and validated. No string interpolation ever.

---

## 📐 Basic Syntax

SMQL uses a pipeline syntax. A pipeline begins with `from` and flows through a series of operators.

```smql
from users
    filter status == user_status.active and age > @min_age
    left join orders as o on users.id == o.user_id
    filter o.created_at > @since
    aggregate total = sum(o.amount) by users.id, users.name, users.country
    sort total desc
    take 10
    select name, country, total
```

A single‑line style with `|` is also planned (optional):

```smql
from users | filter age > 18 | take 10
```

---

## ⚙️ Core Operators

| Operator | Purpose |
|---|---|
| `from` | Starts a pipeline (table, query call, or inline pipeline in `( )`). |
| `filter` | Filters rows (acts like `WHERE` before aggregation, `HAVING` after). |
| `derive` | Creates a computed column. |
| `join` / `left join` / `right join` / `cross join` | Joins two datasets. `on` is required except for `cross join`. |
| `aggregate` | Groups and computes metrics. `by` defines grouping columns. |
| `sort` | Orders rows (`asc` by default, `desc`). |
| `take` | Limits output rows (required unless overridden by policy). |
| `select` | Specifies output columns. |
| `union` | Appends another pipeline result to the current flow. |

---

## 🧱 Expressions

- **Logical:** `and`, `or`, `not` — parentheses only to override precedence.
- **Comparison:** `==`, `!=`, `>`, `<`, `>=`, `<=`.
- **Null checks:** `is null`, `is not null` (not `== null`).
- **Arithmetic:** `+`, `-`, `*`, `/`.
- **String:** `"Hello"`, concatenation with `+`.
- **Aliases:** `as` is heavily encouraged, especially after joins.

```smql
from users as u
    join orders as o on u.id == o.user_id
    select u.name, o.amount
```

---

## 🧪 Type System

| Type | Description | Example |
|---|---|---|
| `string` | Non‑null text | `name: string` |
| `string?` | Nullable text | `nickname: string?` |
| `int` | Integer | `age: int` |
| `decimal(p,s)` | Exact numeric | `price: decimal(12,2)` |
| `bool` | Boolean | `is_active: bool` |
| `date` | Date (no time) | `birth_date: date` |
| `datetime` | Date and time | `created_at: datetime` |
| `uuid` | Universal unique identifier | `id: uuid` |
| `enum` | Predefined set of values | `status: user_status` |

All types are enforced at compile time. Enums prevent "magic string" mistakes.

---

## 📦 Modular Queries

Reusable business logic is defined as query blocks. They require parameter types and a return schema — a clear contract.

```smql
query high_value_customers(
    @min_total: decimal(12,2),
    @country: country_code
) returns {
    name: string,
    country: country_code,
    total: decimal(14,2)
}
    from users as u
        filter u.status == user_status.active
        filter u.country == @country
        join orders as o on u.id == o.user_id
        filter o.status == order_status.paid
        aggregate total = sum(o.amount) by u.id, u.name, u.country
        filter total > @min_total
        select
            name = u.name,
            country = u.country,
            total = total
end
```

To use it:

```smql
from high_value_customers(@min_total=5000, @country=country_code.TR)
    sort total desc
    take 20
```

Queries can be imported from other files:

```smql
import "queries/crm.smql"
```

---

## 📢 Developer Experience

SMQL is built for a feedback‑rich loop, especially when used by AI assistants.

### LLM‑Friendly Error Messages

Instead of `Column not found.`, you get:

```text
Error at line 5, column 12:
  Column `country` is not available after this aggregate step.
  Available fields: users.id, users.name, total
  Possible fixes:
  1. Add `users.country` to the aggregate `by` list
  2. Move `filter country == @ulke` before the aggregate step
```

---

## 🏁 Getting Started

```bash
pip install smql-compiler

# Compile with parameters
smql compile examples/basic.smql --param min_age=18

# Dry run (no parameter values needed)
smql compile examples/basic.smql --dry-run

# Write SQL to a file
smql compile report.smql --param min_age=18 --output report.sql
```

Example output:

```sql
SELECT name, SUM(o.amount) AS total_spent
FROM users
JOIN orders AS o ON users.id = o.user_id
WHERE status = $1 AND age > $2
GROUP BY users.id, users.name
ORDER BY total_spent DESC
LIMIT 10
```

```
Parameters: ['active', 18]
```

---

## 📜 License

This specification is released under the **Creative Commons Attribution 4.0 International License**.
The reference compiler is open‑sourced under the **MIT License**.

---

**SMQL – Write fearlessly, compile safely.**
Brought to you by a community that believes data access should be secure by design.
