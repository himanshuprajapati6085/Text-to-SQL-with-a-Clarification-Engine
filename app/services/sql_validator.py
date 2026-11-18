import re

import sqlglot

from sqlglot import exp

from app.config import settings



class SQLValidationError(Exception):

    pass



META_PATTERNS = [

    ("create_db", re.compile(r"^\s*CREATE\s+DATABASE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$", re.I)),

    ("drop_db", re.compile(r"^\s*DROP\s+DATABASE\s+(?:IF\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$", re.I)),

    ("use_db", re.compile(r"^\s*USE\s+(?:DATABASE\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$", re.I)),

    ("show_dbs", re.compile(r"^\s*SHOW\s+DATABASES\s*;?\s*$", re.I)),

    ("show_tables", re.compile(r"^\s*SHOW\s+TABLES\s*;?\s*$", re.I)),

]



class SQLValidator:

    @classmethod

    def _extract_tables(cls, ast: exp.Expression) -> set[str]:

        return {tbl.name.lower() for tbl in ast.find_all(exp.Table) if tbl.name}



    @classmethod

    def _get_action(cls, ast: exp.Expression) -> str:

        if isinstance(ast, exp.Select):

            return "select"

        if isinstance(ast, exp.Update):

            return "update"

        if isinstance(ast, exp.Insert):

            return "insert"

        if isinstance(ast, exp.Delete):

            return "delete"

        if isinstance(ast, exp.Alter):

            return "alter"

        if isinstance(ast, exp.Create):

            return "create"

        if isinstance(ast, exp.Drop):

            return "drop"

        return ast.key.lower()



    @classmethod

    def parse_meta_command(cls, sql_text: str) -> tuple[str, str | None] | None:

        for cmd_type, pat in META_PATTERNS:

            m = pat.match(sql_text.strip())

            if m:

                arg = m.group(1) if m.lastindex else None

                return cmd_type, arg

        return None



    @classmethod

    def validate_and_format(cls, sql_text: str, role: str = "student", db_name: str = "college") -> tuple[str, str]:

        clean_sql = sql_text.strip().rstrip(";")

        if not clean_sql:

            raise SQLValidationError("Query is empty.")



        # 1. Check Database Meta-Commands first

        meta = cls.parse_meta_command(clean_sql)

        if meta is not None:

            cmd_type, _ = meta

            if role == "teacher":

                raise SQLValidationError(

                    "Permission Denied: Teacher role sirf 'college' database ki 'students' table access kar sakta hai."

                )

            if role == "student" and cmd_type not in {"show_tables"}:

                raise SQLValidationError("Permission Denied: Students sirf Read-Only queries chala sakte hain.")

            return clean_sql, cmd_type



        # 2. Enforce Teacher's strict database lock ('college' only)

        if role == "teacher" and db_name.lower() != "college":

            raise SQLValidationError("Permission Denied: Teacher sirf 'college' database ki 'students' table access kar sakta hai.")



        # 3. Handle SQLite PRAGMA directly for HOD

        if clean_sql.upper().startswith("PRAGMA "):

            if role != "hod":

                raise SQLValidationError("Permission Denied: PRAGMA commands sirf HOD chala sakta hai.")

            return clean_sql, "select"



        # 4. Parse Standard SQL with SQLGlot

        try:

            expressions = sqlglot.parse(clean_sql, read="sqlite")

        except Exception as err:

            raise SQLValidationError(f"SQL Syntax Error: {str(err)}")



        expressions = [e for e in expressions if e is not None]

        if not expressions:

            raise SQLValidationError("Query is empty.")



        if len(expressions) > 1 and role == "student":

            raise SQLValidationError("Multiple statements Students ke liye allowed nahi hain.")



        actions = []

        formatted_stmts = []



        for ast in expressions:

            action = cls._get_action(ast)

            tables = cls._extract_tables(ast)



            # STUDENT: Read-Only (SELECT only)

            if role == "student" and action != "select":

                raise SQLValidationError(

                    f"Permission Denied: Students have Read-Only access. '{action.upper()}' allowed nahi hai."

                )



            # TEACHER: Strictly 'students' table ONLY (Read & Write)

            if role == "teacher":

                if action not in {"select", "insert", "update", "delete"}:

                    raise SQLValidationError(

                        f"Permission Denied: Teacher '{action.upper()}' nahi chala sakta. Sirf students data par SELECT/INSERT/UPDATE/DELETE allowed hai."

                    )

                if not tables or tables != {"students"}:

                    raise SQLValidationError(

                        "Permission Denied: Teacher sirf 'students' table ka data access kar sakta hai, kisi aur table ka nahi."

                    )



            # HOD: Full SQL Access (SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, etc.)

            if action == "select" and not ast.args.get("limit"):

                ast = ast.limit(settings.MAX_RESULT_ROWS)



            actions.append(action)

            formatted_stmts.append(ast.sql(dialect="sqlite"))



        primary_action = actions[-1] if len(set(actions)) > 1 else actions[0]

        return ";\n".join(formatted_stmts), primary_action
