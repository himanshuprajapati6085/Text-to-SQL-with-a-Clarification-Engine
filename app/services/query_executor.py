from typing import Any, Dict, List, Tuple
from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)

class QueryExecutor:
    @staticmethod
    def execute(sql: str, action_type: str) -> Tuple[List[str], List[Dict[str, Any]], str]:
        with engine.begin() as conn:
            # 1. SELECT Query
            if action_type == "select":
                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = []
                for row in result.fetchmany(settings.MAX_RESULT_ROWS):
                    row_dict = {}
                    for col_name, val in zip(columns, row):
                        if hasattr(val, "__float__"):
                            row_dict[col_name] = round(float(val), 2)
                        else:
                            row_dict[col_name] = str(val) if val is not None else None
                    rows.append(row_dict)
                return columns, rows, f"Found {len(rows)} matching record(s)."

            # 2. MULTI-STATEMENT OR SINGLE DML EXECUTION (UPDATE / INSERT / DELETE)
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            total_affected = 0
            for stmt in statements:
                res = conn.execute(text(stmt))
                if hasattr(res, 'rowcount') and res.rowcount is not None and res.rowcount >= 0:
                    total_affected += res.rowcount
                else:
                    total_affected += 1

            if action_type == "insert":
                preview = conn.execute(text("SELECT student_id, name, department_id, marks FROM students ORDER BY student_id DESC LIMIT 10"))
                cols = list(preview.keys())
                preview_rows = [{c: (round(float(v), 2) if hasattr(v, '__float__') else str(v)) for c, v in zip(cols, r)} for r in preview.fetchall()]
                return cols, preview_rows, f"Success: Inserted record(s) into database!"

            elif action_type == "alter":
                preview = conn.execute(text("SELECT * FROM students LIMIT 5"))
                cols = list(preview.keys())
                preview_rows = [{c: str(v) for c, v in zip(cols, r)} for r in preview.fetchall()]
                return cols, preview_rows, "Success: Database schema updated!"

            else: # UPDATE / DELETE
                preview = conn.execute(text("SELECT student_id, name, department_id, marks FROM students ORDER BY student_id ASC LIMIT 10"))
                cols = list(preview.keys())
                preview_rows = [{c: (round(float(v), 2) if hasattr(v, '__float__') else str(v)) for c, v in zip(cols, r)} for r in preview.fetchall()]
                return cols, preview_rows, f"Success: Updated {total_affected} student record(s) across {len(statements)} operation(s)!"
