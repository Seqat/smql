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

## 🔒 Security at the Core

SMQL is **“secure by design”**:

- **AST‑first:** Queries are never built with string concatenation. Input is parsed into an immutable AST before execution.
- **Parameter isolation:** `@user_input` is attached as a value leaf in the AST, never as code.
- **Symbol / value separation:** Table and column names are symbols, not strings. `from @user_table` is syntactically impossible.
- **Enum locking:** Status fields are compared against compile‑time enums (`user_status.active`), not arbitrary strings.
- **Null safety:** `== null` is invalid; you must write `is null` / `is not null`.
- **Sensitive data protection:** Columns can be marked `sensitive`, `pii`, or `secret`. Unauthorized access is blocked at compile time.
- **Policy layer:** Row‑level security, tenant isolation, and custom business rules are defined with `policy` blocks and enforced at the language level.
- **Cost limiting:** A `take` clause is mandatory (or a system‑wide `max_rows` policy applies).
- **Transpiler safety:** Generated SQL is 100% parameterized and validated by a second SQL parser. No string interpolation ever.

---

## 📐 Basic Syntax

SMQL uses **significant indentation** (like Python). A pipeline begins with `from` and flows through a series of operators.

```smql
from users
    filter status == user_status.active and age > @min_age
    left join orders as o on users.id == o.user_id
    filter o.created_at > @since
    aggregate total = sum(o.amount) by users.id, users.name, users.country
    sort total desc
    take 10
    select name, country, total
A single‑line style with | is also allowed (optional):

smql
from users | filter age > 18 | take 10
⚙️ Core Operators
Operator Purpose
from Starts a pipeline (table, query call, or inline pipeline in ( )).
filter Filters rows (acts like WHERE before aggregation, HAVING after).
derive Creates a computed column.
join / left join / right join / cross join Joins two datasets. on is required except for cross join.
aggregate Groups and computes metrics. by defines grouping columns.
sort Orders rows (asc by default, desc).
take Limits output rows (required unless overridden by policy).
select Specifies output columns. select * is prohibited in strict mode.
union Appends another pipeline result to the current flow.
🧱 Expressions
Logical: and, or, not — parentheses only to override precedence.

Comparison: ==, !=, >, <, >=, <=.

Null checks: is null, is not null (not == null).

Arithmetic: +, -, *, /.

String: "Hello", concatenation with +.

Aliases: as is heavily encouraged, especially after joins.

smql
from users as u
    join orders as o on u.id == o.user_id
    select u.name, o.amount
🧪 Type System
Type Description Example
string Non‑null text name: string
string? Nullable text nickname: string?
int Integer age: int
decimal(p,s) Exact numeric price: decimal(12,2)
bool Boolean is_active: bool
date Date (no time) birth_date: date
datetime Date and time created_at: datetime
uuid Universal unique identifier id: uuid
enum Predefined set of values status: user_status
All types are enforced at compile time. Enums prevent “magic string” mistakes.

📦 Modular Queries
Reusable business logic is defined as query blocks. They require parameter types and a return schema — a clear contract.

smql
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
To use it:

smql
from high_value_customers(@min_total=5000, @country=country_code.TR)
    sort total desc
    take 20
Queries can be imported from other files:

smql
import "queries/crm.smql"
🛡️ Security Policies
Row‑level security is declared with policy blocks and enforced by the compiler.

smql
policy tenant_isolation
    require users.tenant_id == @current_tenant_id
end

query list_users(@current_tenant_id: uuid)
    from users
        require policy tenant_isolation
        select id, name, email
end
Attempting to run list_users without a valid policy context results in a compile‑time error.

🔍 Sensitive Column Protection
Schema definitions can mark columns as sensitive:

smql
table users
    id: uuid
    email: string sensitive
    password_hash: string secret
    phone: string pii
end
Selecting a secret column without explicit permission is rejected by the compiler.

📢 Developer Experience
SMQL is built for a feedback‑rich loop, especially when used by AI assistants.

LLM‑Friendly Error Messages
Instead of Column not found., you get:

text
Error at line 5, column 12:
  Column `country` is not available after this aggregate step.
  Available fields: users.id, users.name, total
  Possible fixes:
  1. Add `users.country` to the aggregate `by` list
  2. Move `filter country == @ulke` before the aggregate step
Source Maps
The transpiler emits a source map that maps every SMQL line to the generated SQL line — no more debugging three layers of abstraction.

🗺️ Roadmap (v0.2.0 → future)
✅ Secure pipeline syntax, enums, modular queries

✅ Null safety, sensitive data markers, policies

🔲 Window functions (over, partition by, row_number())

🔲 Recursive queries (recursive query)

🔲 DML support (insert, update, delete)

🔲 Multi‑dialect SQL generation (MySQL, SQLite, DuckDB)

🔲 VS Code extension with LSP (autocomplete, live errors)

🔲 AI integration library (LangChain, LlamaIndex)

🏁 Getting Started (Preview)
bash
pip install smql-compiler
smql compile --target postgres report.smql
Output:

sql
SELECT u.name, u.country, SUM(o.amount) AS total
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.status = $1 AND u.country = $2 AND o.created_at > $3
GROUP BY u.id, u.name, u.country
HAVING SUM(o.amount) > $4
ORDER BY total DESC
LIMIT $5
Parameters: ['active', 'TR', '2025-01-01', 5000, 20]

📜 License
This specification is released under the Creative Commons Attribution 4.0 International License.
The reference compiler will be open‑sourced under the MIT License.

SMQL – Write fearlessly, compile safely.
Brought to you by a community that believes data access should be secure by design.
