from typing import List, Set

from sqlalchemy import inspect

from app.schemas.request_models import ColumnInfo, TableSchema

from app.services.db_manager import DBManager



class SchemaService:

    @staticmethod

    def get_live_schema(db_name: str = "college", role: str = "student") -> List[TableSchema]:

        if role == "teacher":

            db_name = "college"

        engine = DBManager.get_engine(db_name)

        inspector = inspect(engine)

        table_names = [t for t in inspector.get_table_names() if not t.startswith("sqlite_")]



        # Strict Teacher restriction: Only 'students' table is visible/accessible

        if role == "teacher":

            table_names = [t for t in table_names if t.lower() == "students"]



        schema_list = []

        for tbl in table_names:

            cols = [ColumnInfo(name=col["name"], type=str(col["type"])) for col in inspector.get_columns(tbl)]

            schema_list.append(TableSchema(table_name=tbl, columns=cols))

        return schema_list



    @staticmethod

    def get_allowed_tables(db_name: str = "college") -> Set[str]:

        engine = DBManager.get_engine(db_name)

        inspector = inspect(engine)

        return {t.lower() for t in inspector.get_table_names() if not t.startswith("sqlite_")}



    @staticmethod

    def get_ddl_representation(db_name: str = "college", role: str = "student") -> str:

        if role == "teacher":

            db_name = "college"

        engine = DBManager.get_engine(db_name)

        inspector = inspect(engine)

        table_names = [t for t in inspector.get_table_names() if not t.startswith("sqlite_")]

        if role == "teacher":

            table_names = [t for t in table_names if t.lower() == "students"]



        parts = []

        for tbl in table_names:

            cols = [f"  {c['name']} {c['type']}" for c in inspector.get_columns(tbl)]

            parts.append(f"CREATE TABLE {tbl} (\n" + ",\n".join(cols) + "\n);")

        return "\n\n".join(parts) if parts else "-- Database is currently empty (no tables created yet)."
