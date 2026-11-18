import os

import re

from typing import Dict, List

from sqlalchemy import create_engine, Engine, text



DB_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,49}$")



class DBManagerError(Exception):

    pass



class DBManager:

    _engines: Dict[str, Engine] = {}



    @staticmethod

    def validate_db_name(db_name: str) -> str:

        clean = db_name.strip()

        if clean.lower().endswith(".db"):

            clean = clean[:-3]

        if not DB_NAME_PATTERN.match(clean):

            raise DBManagerError(

                f"Invalid database name '{db_name}'. Sirf letters, numbers aur underscore (_) use karein."

            )

        return clean



    @classmethod

    def get_db_path(cls, db_name: str) -> str:

        clean = cls.validate_db_name(db_name)

        return os.path.abspath(f"{clean}.db")



    @classmethod

    def list_databases(cls) -> List[str]:

        dbs = []

        for fname in os.listdir("."):

            if fname.endswith(".db") and os.path.isfile(fname):

                dbs.append(fname[:-3])

        if "college" not in dbs:

            dbs.insert(0, "college")

        # Keep 'college' first, others sorted alphabetically

        others = sorted([d for d in dbs if d != "college"], key=str.lower)

        return ["college"] + others



    @classmethod

    def database_exists(cls, db_name: str) -> bool:

        clean = cls.validate_db_name(db_name)

        return os.path.isfile(f"{clean}.db")



    @classmethod

    def get_engine(cls, db_name: str = "college") -> Engine:

        clean = cls.validate_db_name(db_name)

        if not cls.database_exists(clean) and clean != "college":

            raise DBManagerError(f"Database '{clean}' exist nahi karta. Pehle create karein.")

        if clean not in cls._engines:

            cls._engines[clean] = create_engine(

                f"sqlite:///./{clean}.db",

                connect_args={"check_same_thread": False}

            )

        return cls._engines[clean]



    @classmethod

    def create_database(cls, db_name: str) -> str:

        clean = cls.validate_db_name(db_name)

        if cls.database_exists(clean):

            raise DBManagerError(f"Database '{clean}' pehle se exist karta hai.")

        engine = create_engine(

            f"sqlite:///./{clean}.db",

            connect_args={"check_same_thread": False}

        )

        with engine.begin() as conn:

            conn.execute(text("SELECT 1;"))

        cls._engines[clean] = engine

        return clean



    @classmethod

    def drop_database(cls, db_name: str) -> str:

        clean = cls.validate_db_name(db_name)

        if clean.lower() == "college":

            raise DBManagerError("Main 'college' database delete nahi kiya ja sakta.")

        if not cls.database_exists(clean):

            raise DBManagerError(f"Database '{clean}' exist nahi karta.")

        if clean in cls._engines:

            cls._engines[clean].dispose()

            del cls._engines[clean]

        os.remove(f"{clean}.db")

        return clean
