import re
from typing import Tuple, Optional, Dict, Any, List
import sqlglot
from sqlglot import exp

class PermissionDeniedException(Exception):
    pass

class RLSGuardrail:
    """
    Role-Based Row-Level Security (RLS) & Column-Level Masking Engine.
    Intercepts and rewrites SQL AST using sqlglot before execution.
    """

    @classmethod
    def process_and_enforce(
        cls,
        sql: str,
        role: str,
        user_id: int,
        dept_id: Optional[int],
        course_id: Optional[int],
        linked_profile_id: Optional[int],
        user_name: Optional[str] = None
    ) -> Tuple[str, str, bool]:
        role_upper = (role or "STUDENT").upper()
        clean_sql = sql.strip().rstrip(";")
        if not clean_sql:
            raise PermissionDeniedException("Query is empty.")

        cmd_type = clean_sql.split()[0].upper()

        # 1. Structural Command Check
        if role_upper == "STUDENT":
            if cmd_type not in {"SELECT", "WITH", "EXPLAIN", "PRAGMA", "SHOW"}:
                raise PermissionDeniedException(
                    f"Permission Denied: Students have Read-Only access. Action '{cmd_type}' is blocked."
                )

        if role_upper == "TEACHER":
            if cmd_type in {"DROP", "ALTER", "CREATE"}:
                raise PermissionDeniedException(
                    f"Permission Denied: Teachers cannot perform structural DDL operations like '{cmd_type}'."
                )
            if cmd_type == "DELETE":
                raise PermissionDeniedException(
                    "Permission Denied: Teachers cannot delete student or faculty records. Contact HOD."
                )
            if cmd_type == "INSERT" and "TEACHERS" in clean_sql.upper():
                raise PermissionDeniedException(
                    "Permission Denied: Teachers cannot add faculty members. HOD permission required."
                )

        if role_upper == "HOD":
            if "DROP DATABASE" in clean_sql.upper():
                raise PermissionDeniedException(
                    "Permission Denied: Dropping the college database is restricted."
                )

        # 2. Parse AST
        try:
            ast = sqlglot.parse_one(clean_sql, read="sqlite")
        except Exception as e:
            if re.match(r"^SHOW\s+(?:TABLES|DATABASES)", clean_sql, re.I):
                return clean_sql, "Meta Command (Unmodified)", False
            raise PermissionDeniedException(f"SQL Syntax Validation Error: {str(e)}")

        d_id = dept_id or 1
        st_id = linked_profile_id or 101
        c_id = course_id or 1
        t_id = linked_profile_id or 2

        guardrail_notes = []
        is_modified = False

        # Detect top-level command type and target
        if isinstance(ast, exp.Select):
            table_map = {}
            for tbl in ast.find_all(exp.Table):
                if tbl.name:
                    table_map[tbl.name.lower()] = tbl.alias_or_name

            columns_referenced = {c.name.lower() for c in ast.find_all(exp.Column) if c.name}
            has_star = bool(list(ast.find_all(exp.Star)))
            is_count_query = bool(list(ast.find_all(exp.Count)))

            if role_upper == "STUDENT":
                if "teachers" in table_map:
                    if "salary" in columns_referenced:
                        raise PermissionDeniedException(
                            "Permission Denied: Your role (Student) does not have access to faculty salary records."
                        )
                    if "phone" in columns_referenced:
                        raise PermissionDeniedException(
                            "Permission Denied: Your role (Student) does not have access to faculty personal contact records."
                        )
                    if has_star:
                        alias = table_map.get("teachers", "teachers")
                        cls._replace_star_with_columns(
                            ast,
                            alias,
                            [f"{alias}.teacher_id", f"{alias}.name", f"{alias}.designation", f"{alias}.dept_id", f"{alias}.email"]
                        )
                        guardrail_notes.append("Column Masking: Replaced '*' on teachers with public columns")
                        is_modified = True

                if "students" in table_map:
                    alias = table_map.get("students", "students")
                    if not is_count_query:
                        condition = f"{alias}.student_id = {st_id}"
                        ast.where(condition, copy=False)
                        guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (Self Record Only)")
                        is_modified = True
                    else:
                        condition = f"{alias}.course_id = {c_id}"
                        ast.where(condition, copy=False)
                        guardrail_notes.append(f"Row-Level Security (RLS): Scoped COUNT to course_id = {c_id}")
                        is_modified = True

                if "academic_records" in table_map:
                    alias = table_map.get("academic_records", "academic_records")
                    condition = f"{alias}.student_id = {st_id}"
                    ast.where(condition, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (Personal Records Only)")
                    is_modified = True

            elif role_upper == "TEACHER":
                if "teachers" in table_map:
                    alias = table_map.get("teachers", "teachers")
                    if "salary" in columns_referenced or "phone" in columns_referenced:
                        where_clause = str(ast.args.get("where") or "")
                        if f"{t_id}" not in where_clause:
                            raise PermissionDeniedException(
                                "Permission Denied: Faculty salary records are confidential and restricted to personal view or HOD."
                            )
                    condition = f"{alias}.dept_id = {d_id}"
                    ast.where(condition, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (Department Faculty Isolation)")
                    is_modified = True

                if "students" in table_map:
                    alias = table_map.get("students", "students")
                    condition = f"{alias}.dept_id = {d_id}"
                    ast.where(condition, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (Department Scope)")
                    is_modified = True

                if "academic_records" in table_map and "students" not in table_map:
                    alias = table_map.get("academic_records", "academic_records")
                    subquery = f"{alias}.student_id IN (SELECT student_id FROM students WHERE dept_id = {d_id})"
                    ast.where(subquery, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Scoped academic records to Dept ID {d_id}")
                    is_modified = True

            elif role_upper == "HOD":
                if "students" in table_map:
                    alias = table_map.get("students", "students")
                    condition = f"{alias}.dept_id = {d_id}"
                    ast.where(condition, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (HOD Department Scope)")
                    is_modified = True

                if "teachers" in table_map:
                    alias = table_map.get("teachers", "teachers")
                    condition = f"{alias}.dept_id = {d_id}"
                    ast.where(condition, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (HOD Department Faculty Scope)")
                    is_modified = True

                if "courses" in table_map:
                    alias = table_map.get("courses", "courses")
                    condition = f"{alias}.dept_id = {d_id}"
                    ast.where(condition, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Enforced '{condition}' (HOD Department Courses Scope)")
                    is_modified = True

                if "academic_records" in table_map and "students" not in table_map:
                    alias = table_map.get("academic_records", "academic_records")
                    subquery = f"{alias}.student_id IN (SELECT student_id FROM students WHERE dept_id = {d_id})"
                    ast.where(subquery, copy=False)
                    guardrail_notes.append(f"Row-Level Security (RLS): Scoped academic records to Dept ID {d_id}")
                    is_modified = True

        elif isinstance(ast, (exp.Update, exp.Delete)):
            target_table = ast.this.name.lower() if hasattr(ast.this, "name") else str(ast.this).lower()

            if target_table == "academic_records":
                condition = f"student_id IN (SELECT student_id FROM students WHERE dept_id = {d_id})"
                ast.where(condition, copy=False)
                guardrail_notes.append(f"Row-Level Security (RLS): Scoped UPDATE to Dept ID {d_id}")
                is_modified = True

            elif target_table == "students":
                condition = f"dept_id = {d_id}"
                ast.where(condition, copy=False)
                guardrail_notes.append(f"Row-Level Security (RLS): Scoped operation to Dept ID {d_id}")
                is_modified = True

            elif target_table == "teachers":
                condition = f"dept_id = {d_id}"
                ast.where(condition, copy=False)
                guardrail_notes.append(f"Row-Level Security (RLS): Scoped operation to Dept ID {d_id}")
                is_modified = True

        rewritten_sql = ast.sql("sqlite")
        guardrail_desc = " | ".join(guardrail_notes) if guardrail_notes else "Verified: Query within authorized policy bounds."
        return rewritten_sql, guardrail_desc, is_modified

    @classmethod
    def _replace_star_with_columns(cls, ast: exp.Expression, target_table_alias: str, new_cols: List[str]):
        for select_node in ast.find_all(exp.Select):
            new_expressions = []
            has_star = False
            for expr in select_node.expressions:
                if isinstance(expr, exp.Star):
                    has_star = True
                else:
                    new_expressions.append(expr)
            if has_star:
                for col in new_cols:
                    new_expressions.append(sqlglot.parse_one(col))
                select_node.set("expressions", new_expressions)
