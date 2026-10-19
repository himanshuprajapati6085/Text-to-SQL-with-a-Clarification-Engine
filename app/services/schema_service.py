from typing import Dict, List, Set
from sqlalchemy import create_engine, inspect
from app.config import settings
from app.schemas.request_models import ColumnInfo, TableSchema

engine = create_engine(settings.DATABASE_URL)

class SchemaService:
    @staticmethod
    def get_live_schema() -> List[TableSchema]:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        schema_list = []

        for tbl in table_names:
            cols = []
            for col in inspector.get_columns(tbl):
                cols.append(ColumnInfo(name=col["name"], type=str(col["type"])))
            schema_list.append(TableSchema(table_name=tbl, columns=cols))
        return schema_list

    @staticmethod
    def get_allowed_tables() -> Set[str]:
        inspector = inspect(engine)
        return {t.lower() for t in inspector.get_table_names()}

    @staticmethod
    def get_allowed_columns_for_table(table_name: str) -> Set[str]:
        inspector = inspect(engine)
        tables = {t.lower(): t for t in inspector.get_table_names()}
        if table_name.lower() not in tables:
            return set()
        actual_name = tables[table_name.lower()]
        return {col["name"].lower() for col in inspector.get_columns(actual_name)}

    @staticmethod
    def get_ddl_representation() -> str:
        inspector = inspect(engine)
        parts = []
        for tbl in inspector.get_table_names():
            cols = [f"  {c['name']} {c['type']}" for c in inspector.get_columns(tbl)]
            parts.append(f"CREATE TABLE {tbl} (\n" + ",\n".join(cols) + "\n);")
        return "\n\n".join(parts)
