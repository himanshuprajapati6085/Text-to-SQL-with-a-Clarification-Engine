import os

import re

from typing import Any, Dict, List, Tuple

from sqlalchemy import inspect, text

from app.config import settings

from app.services.db_manager import DBManager, DBManagerError

from app.services.sql_validator import SQLValidator



class QueryExecutor:

    @staticmethod

    def _format_val(val: Any) -> Any:

        if val is None:

            return None

        if isinstance(val, float):

            return round(val, 2)

        if isinstance(val, int):

            return val

        return str(val)



    @staticmethod

    def _detect_target_table(sql: str) -> str | None:

        m = re.search(

            r"(?:CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?|INSERT\s+INTO|UPDATE|DELETE\s+FROM|ALTER\s+TABLE)\s+([A-Za-z_][A-Za-z0-9_]*)",

            sql,

            re.I,

        )

        return m.group(1) if m else None



    @classmethod

    def execute(cls, sql: str, action_type: str, db_name: str = "college") -> Tuple[List[str], List[Dict[str, Any]], str, str]:

        # 1. Handle Database Meta-Commands

        meta = SQLValidator.parse_meta_command(sql)

        if meta is not None:

            cmd_type, arg = meta

            if cmd_type == "create_db":

                created = DBManager.create_database(arg)

                rows = [{"database_name": d, "status": "ACTIVE" if d == created else "READY"} for d in DBManager.list_databases()]

                return ["database_name", "status"], rows, f"Success: New database '{created}' ({created}.db) created and selected!", created



            if cmd_type == "use_db":

                target = DBManager.validate_db_name(arg)

                if not DBManager.database_exists(target):

                    raise DBManagerError(f"Database '{target}' exist nahi karta.")

                engine = DBManager.get_engine(target)

                with engine.connect() as conn:

                    res = conn.execute(text("SELECT name AS table_name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))

                    rows = [{"table_name": r[0]} for r in res.fetchall()]

                return ["table_name"], rows, f"Switched active database to '{target}' ({target}.db).", target



            if cmd_type == "drop_db":

                dropped = DBManager.drop_database(arg)

                new_active = "college" if db_name == dropped else db_name

                rows = [{"database_name": d} for d in DBManager.list_databases()]

                return ["database_name"], rows, f"Deleted database '{dropped}' ({dropped}.db).", new_active



            if cmd_type == "show_dbs":

                rows = []

                for d in DBManager.list_databases():

                    path = DBManager.get_db_path(d)

                    size_kb = round(os.path.getsize(path) / 1024, 2) if os.path.exists(path) else 0

                    tbl_count = len([t for t in inspect(DBManager.get_engine(d)).get_table_names() if not t.startswith("sqlite_")])

                    rows.append({"database_name": d, "file": f"{d}.db", "tables": tbl_count, "size_kb": size_kb, "active": "YES" if d == db_name else ""})

                return ["database_name", "file", "tables", "size_kb", "active"], rows, f"Found {len(rows)} database(s).", db_name



            if cmd_type == "show_tables":

                engine = DBManager.get_engine(db_name)

                with engine.connect() as conn:

                    res = conn.execute(text("SELECT name AS table_name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))

                    rows = [{"table_name": r[0]} for r in res.fetchall()]

                return ["table_name"], rows, f"Found {len(rows)} table(s) in '{db_name}.db'.", db_name



        # 2. Standard SQL Execution on active SQLite database

        engine = DBManager.get_engine(db_name)

        with engine.begin() as conn:

            if action_type == "select":

                result = conn.execute(text(sql))

                columns = list(result.keys())

                rows = [

                    {col: cls._format_val(val) for col, val in zip(columns, row)}

                    for row in result.fetchmany(settings.MAX_RESULT_ROWS)

                ]

                return columns, rows, f"Fetched {len(rows)} record(s) from '{db_name}.db'.", db_name



            statements = [s.strip() for s in sql.split(";") if s.strip()]

            total_affected = 0

            last_target_table = None

            for stmt in statements:

                res = conn.execute(text(stmt))

                if hasattr(res, "rowcount") and res.rowcount is not None and res.rowcount >= 0:

                    total_affected += res.rowcount

                tbl = cls._detect_target_table(stmt)

                if tbl:

                    last_target_table = tbl



            # If last statement was SELECT in a multi-statement batch

            if statements[-1].upper().startswith("SELECT"):

                res_sel = conn.execute(text(statements[-1]))

                cols = list(res_sel.keys())

                rows = [{c: cls._format_val(v) for c, v in zip(cols, r)} for r in res_sel.fetchmany(settings.MAX_RESULT_ROWS)]

                return cols, rows, f"Executed {len(statements)} statements in '{db_name}.db'.", db_name



            # Check if target table still exists (if not dropped)

            existing_tables = [

                r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")).fetchall()

            ]



            if last_target_table and any(t.lower() == last_target_table.lower() for t in existing_tables):

                actual_tbl = next(t for t in existing_tables if t.lower() == last_target_table.lower())

                preview = conn.execute(text(f"SELECT * FROM {actual_tbl} LIMIT {settings.MAX_RESULT_ROWS}"))

                cols = list(preview.keys())

                preview_rows = [{c: cls._format_val(v) for c, v in zip(cols, r)} for r in preview.fetchall()]

                msg = f"Success in '{db_name}.db' -> table '{actual_tbl}' ({action_type.upper()}, {total_affected} row(s) affected)."

                return cols, preview_rows, msg, db_name



            # For DROP TABLE or schema commands without previewable target table

            tbl_rows = [{"table_name": t} for t in existing_tables]

            return ["table_name"], tbl_rows, f"Operation ({action_type.upper()}) completed in '{db_name}.db'.", db_name
