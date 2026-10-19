import sqlglot
from sqlglot import exp
from app.config import settings

class SQLValidationError(Exception):
    pass

class SQLValidator:
    @classmethod
    def validate_and_format(cls, sql_text: str, role: str = "student") -> tuple[str, str]:
        clean_sql = sql_text.strip().rstrip(";")
        if not clean_sql:
            raise SQLValidationError("Query is empty.")

        try:
            expressions = sqlglot.parse(clean_sql)
        except Exception as err:
            raise SQLValidationError(f"SQL Syntax Error: {str(err)}")

        if not expressions or expressions[0] is None:
            raise SQLValidationError("Query is empty.")

        # Multi-statement check
        if len(expressions) > 1:
            if role != "associate":
                raise SQLValidationError("Multiple statements are only permitted for College Associates.")
            for ast in expressions:
                if isinstance(ast, exp.Drop) and "database" in clean_sql.lower():
                    raise SQLValidationError("Dropping database is prohibited.")
            return clean_sql, "update"

        ast = expressions[0]

        if isinstance(ast, exp.Select):
            action_type = "select"
        elif isinstance(ast, exp.Update):
            action_type = "update"
        elif isinstance(ast, exp.Insert):
            action_type = "insert"
        elif isinstance(ast, exp.Delete):
            action_type = "delete"
        elif isinstance(ast, exp.Alter):
            action_type = "alter"
        elif isinstance(ast, exp.Create):
            action_type = "create"
        else:
            action_type = ast.key.lower()

        if role == "student" and action_type != "select":
            raise SQLValidationError(
                f"Action blocked: Students have Read-Only permissions. '{action_type.upper()}' is not permitted."
            )

        if isinstance(ast, exp.Drop) and "database" in clean_sql.lower():
            raise SQLValidationError("Dropping database is prohibited.")

        if action_type == "select":
            limit_node = ast.args.get("limit")
            if not limit_node:
                ast = ast.limit(settings.MAX_RESULT_ROWS)

        return ast.sql(), action_type
