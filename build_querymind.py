import os
import sys

# Ensure UTF-8 output in Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
FILES = {}



# 1. requirements.txt

FILES["requirements.txt"] = r"""fastapi>=0.110.0

uvicorn[standard]>=0.28.0

sqlalchemy>=2.0.28

sqlglot>=23.0.0

pydantic>=2.6.0

pydantic-settings>=2.2.1

openai>=1.14.0

httpx>=0.27.0

"""



# 2. .env

FILES[".env"] = r"""APP_ENV=development

HOST=127.0.0.1

PORT=8000

DATABASE_URL=sqlite:///./college.db

LLM_API_KEY=mock-key-development

LLM_MODEL=gpt-4o-mini

LLM_BASE_URL=https://api.openai.com/v1

MAX_RESULT_ROWS=200

QUERY_TIMEOUT_SECONDS=5

"""



# 3. app/config.py

FILES["app/config.py"] = r'''from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):

    APP_ENV: str = "development"

    HOST: str = "127.0.0.1"

    PORT: int = 8000

    DATABASE_URL: str = "sqlite:///./college.db"

    LLM_API_KEY: str = "mock-key-development"

    LLM_MODEL: str = "gpt-4o-mini"

    LLM_BASE_URL: str = "https://api.openai.com/v1"

    MAX_RESULT_ROWS: int = 200

    QUERY_TIMEOUT_SECONDS: int = 5



    model_config = SettingsConfigDict(env_file=".env", extra="ignore")



settings = Settings()

'''



# 4. app/services/db_manager.py (Multi-Database SQLite Manager)

FILES["app/services/db_manager.py"] = r'''import os

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

'''



# 5. init_db.py (Clean persistent college.db)

FILES["init_db.py"] = r'''from sqlalchemy import text

from app.services.db_manager import DBManager



def init_database():

    engine = DBManager.get_engine("college")

    with engine.begin() as conn:

        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS departments (

                department_id INTEGER PRIMARY KEY AUTOINCREMENT,

                department_name VARCHAR(100) NOT NULL UNIQUE

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS teachers (

                teacher_id INTEGER PRIMARY KEY AUTOINCREMENT,

                name VARCHAR(100) NOT NULL,

                subject VARCHAR(100),

                department_id INTEGER,

                email VARCHAR(120),

                FOREIGN KEY (department_id) REFERENCES departments(department_id)

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS students (

                student_id INTEGER PRIMARY KEY AUTOINCREMENT,

                name VARCHAR(100) NOT NULL,

                department_id INTEGER,

                marks REAL,

                attendance REAL,

                FOREIGN KEY (department_id) REFERENCES departments(department_id)

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS courses (

                course_id INTEGER PRIMARY KEY AUTOINCREMENT,

                course_name VARCHAR(100) NOT NULL,

                department_id INTEGER,

                teacher_id INTEGER,

                FOREIGN KEY (department_id) REFERENCES departments(department_id),

                FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)

            );

        """))



        conn.execute(text("""

            CREATE TABLE IF NOT EXISTS enrollments (

                enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,

                student_id INTEGER NOT NULL,

                course_id INTEGER NOT NULL,

                grade VARCHAR(10),

                FOREIGN KEY (student_id) REFERENCES students(student_id),

                FOREIGN KEY (course_id) REFERENCES courses(course_id)

            );

        """))



    print("[OK] Clean SQLite database ready: college.db")



if __name__ == "__main__":

    init_database()

'''



# 6. app/schemas/request_models.py

FILES["app/schemas/request_models.py"] = r'''from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field



class QueryRequest(BaseModel):

    question: str = Field(..., min_length=1, max_length=3000)

    role: str = Field("student", description="'student', 'teacher', or 'hod'")

    mode: str = Field("nl", description="'nl' or 'sql'")

    database: str = Field("college", description="Active SQLite database name")



class CreateDatabaseRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=50)

    role: str = Field("hod")



class ClassificationResult(BaseModel):

    intent: str

    complexity: str

    requires_join: bool

    risk_level: str

    confidence: float

    source: str

    reasoning: Optional[str] = None



class ColumnInfo(BaseModel):

    name: str

    type: str



class TableSchema(BaseModel):

    table_name: str

    columns: List[ColumnInfo]



class SchemaResponse(BaseModel):

    database: str

    databases: List[str]

    tables: List[TableSchema]



class QueryResponse(BaseModel):

    question: str

    intent: str

    complexity: str

    requires_join: bool

    classification_source: str

    sql: str

    action_type: str

    active_database: str

    databases: List[str]

    columns: List[str]

    rows: List[Dict[str, Any]]

    row_count: int

    message: Optional[str] = None

    status: str

    generation_ms: float

    execution_ms: float

    total_ms: float

'''



# 7. app/services/schema_service.py

FILES["app/services/schema_service.py"] = r'''from typing import List, Set

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

'''



# 8. app/services/classifier.py

FILES["app/services/classifier.py"] = r'''import re

from typing import Optional

from app.schemas.request_models import ClassificationResult



class HybridClassifier:

    @classmethod

    def evaluate_rules(cls, text: str, role: str = "student") -> Optional[ClassificationResult]:

        normalized = text.strip().lower()



        # Check database/DDL/DML modification intent

        is_db_or_ddl = any(

            re.search(pat, normalized)

            for pat in [

                r"\bcreate\s+(?:new\s+)?database\b",

                r"\bnew\s+database\b",

                r"\bnaya\s+database\b",

                r"\bdrop\s+database\b",

                r"\bcreate\s+(?:new\s+)?table\b",

                r"\bdrop\s+table\b",

                r"\balter\s+table\b",

                r"\btruncate\b",

                r"\buse\s+(?:database\s+)?\w+",

            ]

        )



        mod_keywords = [

            "change", "update", "replace", "set", "modify", "edit",

            "badal", "badlo", "kardo", "kar do", "बदलो", "करो", "अपडेट",

            "add", "insert", "create", "naya", "nayi", "डालो", "जोड़ो", "नया",

            "delete", "remove", "hatao", "mitao", "हटाओ", "मिटाओ", "alter", "drop"

        ]

        is_mod = is_db_or_ddl or any(

            re.search(rf"\b{re.escape(k)}\b", normalized) if k.isascii() else (k in normalized)

            for k in mod_keywords

        )



        # Prevent false positive when user asks "show" / "dikhao"

        if re.match(r"^(show|list|display|get|find|dikhao|batao|dekho|select|दिखाओ|बताओ)\b", normalized):

            if not is_db_or_ddl and not any(

                re.search(rf"\b{w}\b", normalized)

                for w in ["add", "insert", "update", "delete", "change", "replace", "remove", "drop", "create", "alter"]

            ):

                is_mod = False



        if is_mod:

            if role == "student":

                return ClassificationResult(

                    intent="student_modification_blocked",

                    complexity="medium",

                    requires_join=False,

                    risk_level="high",

                    confidence=1.0,

                    source="rule",

                    reasoning="Students have Read-Only permissions."

                )

            return ClassificationResult(

                intent="data_modification",

                complexity="medium",

                requires_join=False,

                risk_level="low",

                confidence=0.98,

                source="rule",

                reasoning=f"Authorized for {role.upper()}."

            )



        return ClassificationResult(

            intent="projection",

            complexity="simple",

            requires_join=False,

            risk_level="low",

            confidence=0.95,

            source="rule",

            reasoning="Retrieval query."

        )

'''



# 9. app/services/llm_service.py (Handles DB cmds, DDL, Dynamic Tables, English/Hindi/Hinglish)

FILES["app/services/llm_service.py"] = r'''import re

from openai import OpenAI

from app.config import settings

from app.schemas.request_models import ClassificationResult

from app.services.schema_service import SchemaService





class QueryGenerationError(Exception):

    pass





def transliterate_hindi(text: str) -> str:

    if not any(0x0900 <= ord(c) <= 0x097F for c in text):

        return text



    h_map = {

        "अ": "A", "आ": "Aa", "इ": "I", "ई": "Ee", "उ": "U", "ऊ": "Oo",

        "ए": "E", "ऐ": "Ai", "ओ": "O", "औ": "Au",

        "क": "k", "ख": "kh", "ग": "g", "घ": "gh",

        "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",

        "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",

        "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",

        "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",

        "य": "y", "र": "r", "ल": "l", "व": "v",

        "श": "sh", "ष": "sh", "स": "s", "ह": "h",

        "ा": "a", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo",

        "े": "e", "ै": "ai", "ो": "o", "ौ": "au",

        "ं": "n", "ँ": "n", "्": ""

    }

    res = []

    consonants = set("कखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह")

    chars = list(text)

    for i, c in enumerate(chars):

        if c in h_map:

            res.append(h_map[c])

            if c in consonants and i + 1 < len(chars) and chars[i + 1] in consonants:

                res.append("a")

        else:

            res.append(c)

    clean_name = "".join(res).strip().title()

    return clean_name if clean_name else text





def sql_str(val: str) -> str:

    return val.replace("'", "''").strip()





def extract_quoted_value(text: str) -> str:

    clean = text.replace("“", '"').replace("”", '"').replace("’", "'")

    m = re.search(r'"([^"]+)"', clean)

    if m:

        return m.group(1).strip()

    m2 = re.search(r"'([^']+)'", clean)

    if m2:

        return m2.group(1).strip()

    return ""





def detect_target_table(q_lower: str, available_tables: set[str]) -> str:

    # 1. Exact match against tables currently in active database (word boundaries!)

    for tbl in sorted(available_tables, key=len, reverse=True):

        if re.search(rf"\b{re.escape(tbl)}\b", q_lower):

            return tbl

        if tbl.endswith("s") and re.search(rf"\b{re.escape(tbl[:-1])}\b", q_lower):

            return tbl



    # 2. Hindi/Hinglish synonyms

    if re.search(r"\b(teacher|teachers|faculty)\b", q_lower) or "शिक्षक" in q_lower or "टीचर" in q_lower:

        return "teachers"

    if re.search(r"\b(department|departments|dept)\b", q_lower) or "विभाग" in q_lower:

        return "departments"

    if re.search(r"\b(course|courses)\b", q_lower) or "कोर्स" in q_lower:

        return "courses"

    if re.search(r"\b(enrollment|enrollments|grade)\b", q_lower):

        return "enrollments"

    if "students" in available_tables:

        return "students"

    if available_tables:

        return sorted(available_tables)[0]

    return "students"





def get_ordinal_offset(text: str) -> int | None:

    lower = text.lower()

    m = re.search(r"\b(\d+)(?:st|nd|rd|th)\b", lower)

    if m:

        return max(0, int(m.group(1)) - 1)

    words = {

        "first": 0, "pehla": 0, "pehle": 0,

        "second": 1, "doosra": 1, "dusre": 1,

        "third": 2, "teesra": 2, "teesre": 2,

        "fourth": 3, "chautha": 3,

        "fifth": 4, "panchva": 4,

    }

    for w, off in words.items():

        if re.search(rf"\b{w}\b", lower):

            return off

    return None





def parse_local_create_table(clean_q: str) -> str:

    # Raw SQL style: CREATE TABLE foo (...)

    if re.match(r"^\s*CREATE\s+TABLE\s+", clean_q, re.I) and "(" in clean_q:

        return clean_q



    # Natural language style: "create table pass_students with name, marks, grade"

    m = re.search(

        r"create\s+(?:new\s+)?table\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:with|having|columns?)?\s*(.+)?$",

        clean_q,

        re.I,

    )

    if not m:

        raise QueryGenerationError('Table create karne ke liye likhein: create table pass_list with name, marks')



    tbl_name = m.group(1).strip()

    cols_raw = (m.group(2) or "").strip()

    if not cols_raw:

        return f"CREATE TABLE {tbl_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"



    raw_parts = [c.strip() for c in re.split(r"[,&]|\band\b", cols_raw, flags=re.I) if c.strip()]

    col_defs = []

    has_pk = False

    for part in raw_parts:

        # Remove noise words

        col = re.sub(r"^(?:column|columns|field|fields)\s+", "", part.strip(), flags=re.I)

        col_clean = re.sub(r"[^A-Za-z0-9_]", "_", col).strip("_").lower()

        if not col_clean:

            continue

        if col_clean in {"id", f"{tbl_name}_id"} and not has_pk:

            col_defs.append(f"{col_clean} INTEGER PRIMARY KEY AUTOINCREMENT")

            has_pk = True

        elif any(k in col_clean for k in ["marks", "score", "attendance", "percent", "cgpa", "fee"]):

            col_defs.append(f"{col_clean} REAL")

        elif any(k in col_clean for k in ["age", "roll", "year", "count", "department_id", "student_id", "teacher_id"]):

            col_defs.append(f"{col_clean} INTEGER")

        else:

            col_defs.append(f"{col_clean} TEXT")



    if not col_defs:

        col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT", "name TEXT"]

    elif not has_pk:

        col_defs.insert(0, "id INTEGER PRIMARY KEY AUTOINCREMENT")



    return f"CREATE TABLE {tbl_name} ({', '.join(col_defs)})"





def parse_local_insert(clean_q: str, table: str, db_name: str) -> str:

    q_low = clean_q.lower()

    cols = []

    vals = []



    if table == "departments":

        dept_name = extract_quoted_value(clean_q)

        if not dept_name:

            m = re.search(r"(?:department|dept)\s+(?:name\s+)?(?:is\s+|to\s+)?([A-Za-z0-9 &]+?)(?:\s+id|\s+kar|\s*$)", clean_q, re.I)

            if m:

                dept_name = m.group(1).strip()

        if not dept_name:

            raise QueryGenerationError('Department ka naam quotes mein likhein, jaise: add department "Computer Science"')

        return f"INSERT INTO departments (department_name) VALUES ('{sql_str(dept_name)}')"



    # Check if custom table exists in active DB

    schema_list = SchemaService.get_live_schema(db_name, role="hod")

    table_cols = []

    for t in schema_list:

        if t.table_name.lower() == table.lower():

            table_cols = [c.name.lower() for c in t.columns]

            break



    # Generic column=value extraction for custom tables or students/teachers

    name = extract_quoted_value(clean_q)

    if not name:

        m = re.search(

            r"(?:name|naam)\s*(?:is|=|:)?\s*([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s]{1,40}?)(?=\s+(?:marks?|number|score|subject|email|dept|department|id|attendance|roll|grade|kar|and|aur)\b|$)",

            clean_q,

            re.I,

        )

        if m:

            name = m.group(1).strip()

        else:

            m2 = re.search(

                r"(?:add|insert|naya|new)\s+(?:into\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\s+)?([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s]{1,35}?)(?=\s+(?:marks?|number|score|subject|email|dept|department|id|attendance|roll|grade|kar|and|aur)\b|$)",

                clean_q,

                re.I,

            )

            if m2:

                cand = m2.group(1).strip()

                if cand.lower() not in {"student", "students", "teacher", "teachers", "record", "data", "entry", table.lower()}:

                    name = cand



    if not name and ("name" in table_cols or not table_cols):

        raise QueryGenerationError(

            f'Entry add karne ke liye naam likhna zaroori hai. Example: add into {table} "Prem Prajapati" marks 92'

        )



    if name:

        name = transliterate_hindi(name)

        cols.append("name")

        vals.append(f"'{sql_str(name)}'")



    # Match any numeric/text columns present in table_cols

    for col_name in table_cols:

        if col_name in {"id", "student_id", "teacher_id", "name"}:

            continue

        m_num = re.search(rf"\b{re.escape(col_name)}\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)\b", q_low)

        if m_num:

            cols.append(col_name)

            vals.append(m_num.group(1))

            continue

        m_str = re.search(rf'\b{re.escape(col_name)}\s*(?:is|=|:)?\s*"([^"]+)"', clean_q, re.I)

        if m_str:

            cols.append(col_name)

            vals.append(f"'{sql_str(m_str.group(1))}'")



    # Fallback aliases for marks / department_id / subject / email

    if "marks" in table_cols and "marks" not in cols:

        m_mk = re.search(r"\b(?:mark|marks|number|score)\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)\b", q_low)

        if m_mk:

            cols.append("marks")

            vals.append(m_mk.group(1))



    if "department_id" in table_cols and "department_id" not in cols:

        m_dp = re.search(r"\b(?:dept|department)(?:\s+id)?\s*(?:is|=|:)?\s*(\d+)\b", q_low)

        if m_dp:

            cols.append("department_id")

            vals.append(m_dp.group(1))



    if "email" in table_cols and "email" not in cols:

        m_em = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", clean_q)

        if m_em:

            cols.append("email")

            vals.append(f"'{sql_str(m_em.group(1))}'")



    if not cols:

        raise QueryGenerationError(f"'{table}' mein add karne ke liye columns aur values specify karein.")



    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)})"





def parse_local_update_clause(clause: str, default_table: str, available_tables: set[str]) -> str:

    clean = clause.replace("“", '"').replace("”", '"').replace("’", "'").strip()

    lower = clean.lower()

    table = detect_target_table(lower, available_tables) if any(

        re.search(rf"\b{t}\b", lower) for t in (available_tables | {"student", "teacher", "department", "course"})

    ) else default_table

    pk_col = "teacher_id" if table == "teachers" else ("department_id" if table == "departments" else ("student_id" if table == "students" else "id"))



    if any(w in lower for w in ["mark", "number", "score", "attendance"]):

        col_to_set = "attendance" if "attendance" in lower else "marks"

        val_num = None

        for m in re.finditer(r"\b(\d+(?:\.\d+)?)\b", clean):

            prefix = lower[max(0, m.start() - 10):m.start()]

            if "id" not in prefix:

                val_num = m.group(1)

        if not val_num:

            raise QueryGenerationError(f"Update karne ke liye naya {col_to_set} number batayein.")



        offset = get_ordinal_offset(lower)

        if offset is not None:

            return f"UPDATE {table} SET {col_to_set} = {val_num} WHERE {pk_col} = (SELECT {pk_col} FROM {table} ORDER BY {pk_col} ASC LIMIT 1 OFFSET {offset})"



        id_m = re.search(r"\bid\s*(?:is|=|:)?\s*(\d+)\b", lower)

        if id_m:

            return f"UPDATE {table} SET {col_to_set} = {val_num} WHERE {pk_col} = {id_m.group(1)}"



        name_m = re.search(r"(?:of|for|student)\s+([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s]{1,40}?)(?=\s+(?:is|to|=|marks?|attendance|ka|ke|ki)\b|$)", clean, re.I)

        if name_m:

            target_name = transliterate_hindi(name_m.group(1).strip())

            return f"UPDATE {table} SET {col_to_set} = {val_num} WHERE LOWER(name) LIKE '%{sql_str(target_name.lower())}%'"



        raise QueryGenerationError("Kis record ke marks/attendance change karne hain, uska naam ya ID batayein.")



    new_name = extract_quoted_value(clean)

    if not new_name:

        m = re.search(r"(?:to|with|as|naam)\s+([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s]{1,40}?)(?:\s+(?:kar|kardo|kar do|please)\b|$)", clean, re.I)

        if m:

            new_name = m.group(1).strip()



    if not new_name:

        raise QueryGenerationError('Naya naam quotes mein likhein, jaise: change student id 1 name to "Rahul"')



    new_name = transliterate_hindi(new_name)

    offset = get_ordinal_offset(lower)

    if offset is not None:

        return f"UPDATE {table} SET name = '{sql_str(new_name)}' WHERE {pk_col} = (SELECT {pk_col} FROM {table} ORDER BY {pk_col} ASC LIMIT 1 OFFSET {offset})"



    id_m = re.search(r"\bid\s*(?:is|=|:)?\s*(\d+)\b", lower)

    if id_m:

        return f"UPDATE {table} SET name = '{sql_str(new_name)}' WHERE {pk_col} = {id_m.group(1)}"



    old_m = re.search(r"(?:of|from)\s+([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s]{1,40}?)(?=\s+(?:to|with|as)\b)", clean, re.I)

    if old_m:

        old_name = transliterate_hindi(old_m.group(1).strip())

        return f"UPDATE {table} SET name = '{sql_str(new_name)}' WHERE LOWER(name) LIKE '%{sql_str(old_name.lower())}%'"



    raise QueryGenerationError("Update karne ke liye target record ki ID, position, ya purana naam batayein.")





class LLMService:

    def __init__(self):

        self.is_mock = "mock" in settings.LLM_API_KEY.lower() or len(settings.LLM_API_KEY.strip()) < 10

        if not self.is_mock:

            self.client = OpenAI(

                api_key=settings.LLM_API_KEY,

                base_url=settings.LLM_BASE_URL

            )

        self.model = settings.LLM_MODEL



    def classify_question(self, question: str, role: str = "student") -> ClassificationResult:

        return ClassificationResult(

            intent="projection",

            complexity="simple",

            requires_join=False,

            risk_level="low",

            confidence=0.95,

            source="rule",

            reasoning="Default classification"

        )



    def generate_sql(self, question: str, classification: ClassificationResult, role: str = "student", db_name: str = "college") -> str:

        clean_q = question.replace("“", '"').replace("”", '"').replace("’", "'").strip()

        q = clean_q.lower()



        # 0. Database-level Meta Commands (Handled cleanly for both AI and Local mode!)

        m_cdb = re.match(r"^(?:please\s+)?(?:create|make|add|banao)\s+(?:a\s+)?(?:new\s+)?database\s+(?:named\s+|called\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*;?$", clean_q, re.I)

        if m_cdb:

            return f"CREATE DATABASE {m_cdb.group(1)}"

        if re.match(r"^(?:naya|new)\s+database\s+([A-Za-z_][A-Za-z0-9_]*)", clean_q, re.I):

            db_n = re.match(r"^(?:naya|new)\s+database\s+([A-Za-z_][A-Za-z0-9_]*)", clean_q, re.I).group(1)

            return f"CREATE DATABASE {db_n}"



        m_udb = re.match(r"^(?:use|switch\s+to|open|select)\s+database\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?$", clean_q, re.I)

        if m_udb:

            return f"USE DATABASE {m_udb.group(1)}"



        m_ddb = re.match(r"^(?:drop|delete|remove)\s+database\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?$", clean_q, re.I)

        if m_ddb:

            return f"DROP DATABASE {m_ddb.group(1)}"



        if re.search(r"\b(?:show|list|all|sabhi|saare)\s+databases?\b", q):

            return "SHOW DATABASES"



        if re.search(r"\b(?:show|list|all|sabhi|saare)\s+tables?\b", q):

            return "SHOW TABLES"



        # If user wrote valid raw SQL directly even in AI Prompt mode, pass it through!
        # Note: If CREATE TABLE has no '(', it is natural language (e.g. 'create table foo with bar, baz')
        is_raw_create = bool(re.match(r"^\s*CREATE\s+TABLE\b", clean_q, re.I) and "(" in clean_q)
        is_other_raw = bool(re.match(r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|ALTER|DROP|PRAGMA|WITH)\b", clean_q, re.I) and not re.match(r"^\s*CREATE\s+TABLE\b", clean_q, re.I))
        if is_raw_create or is_other_raw:
            return clean_q



        # 1. REAL AI MODE (High Accuracy for English, Hindi & Hinglish)

        if not self.is_mock:

            ddl = SchemaService.get_ddl_representation(db_name=db_name, role=role)

            sys_prompt = f"""You are a high-accuracy SQLite Text-to-SQL engine for a Multi-Database College Management System.

Current Active Database: {db_name}

User Role: {role.upper()}



Live Schema of '{db_name}':

{ddl}



STRICT RULES:

1. Understand English, Hindi (Devanagari), and Hinglish seamlessly.

2. NEVER invent or assume extra data! Only insert or update exact columns and values explicitly provided by the user.

3. Support full SQLite capabilities for HOD (CREATE TABLE, ALTER TABLE, DROP TABLE, INSERT, UPDATE, DELETE, SELECT, aggregations, joins).

4. For database-level actions, you may output: CREATE DATABASE <name>, USE DATABASE <name>, DROP DATABASE <name>, SHOW DATABASES, SHOW TABLES.

5. For Teacher role: ONLY generate queries targeting the 'students' table. If Teacher asks for any other table (like teachers/departments), reply: ERROR: Teachers can only access the 'students' table.

6. If the request is missing required data (e.g., adding a record without a name), reply ONLY with: ERROR: <clear reason>.

7. Output ONLY raw SQL with no markdown fences or explanation."""



            res = self.client.chat.completions.create(

                model=self.model,

                messages=[

                    {"role": "system", "content": sys_prompt},

                    {"role": "user", "content": question}

                ],

                temperature=0.0

            )

            sql = res.choices[0].message.content.strip()

            if sql.startswith("```"):

                sql = "\n".join([line for line in sql.split("\n") if not line.startswith("```")]).strip()

            if sql.upper().startswith("ERROR:"):

                raise QueryGenerationError(sql[6:].strip())

            return sql



        # 2. CLEAN LOCAL ENGINE (When API key is mock)

        available_tables = SchemaService.get_allowed_tables(db_name)



        # CREATE TABLE

        if re.search(r"\bcreate\s+(?:new\s+)?table\b", q):

            return parse_local_create_table(clean_q)



        # DROP TABLE

        m_dt = re.match(r"^(?:drop|delete|remove)\s+table\s+([A-Za-z_][A-Za-z0-9_]*)", clean_q, re.I)

        if m_dt:

            return f"DROP TABLE {m_dt.group(1)}"



        # Teacher explicit guard in local mode

        if role == "teacher" and any(re.search(rf"\b{t}\b", q) for t in ["teacher", "teachers", "department", "departments", "course", "courses", "enrollment", "enrollments"]):

            return "SELECT * FROM teachers"  # SQLValidator will immediately block with clear 403 Permission Denied!



        table = detect_target_table(q, available_tables)



        # UPDATE

        if any(re.search(rf"\b{w}\b", q) for w in ["change", "update", "replace", "modify", "badal", "badlo"]) or any(w in question for w in ["बदलो", "अपडेट"]):

            if (" and " in q or " aur " in q) and any(w in q for w in ["student", "teacher", "marks", "name", "1st", "2nd", "3rd", "4th"]):

                parts = re.split(r"\s+(?:and|aur)\s+", clean_q, flags=re.I)

                stmts = [parse_local_update_clause(p, table, available_tables) for p in parts if p.strip()]

                return ";\n".join(stmts)

            return parse_local_update_clause(clean_q, table, available_tables)



        # INSERT

        if any(re.search(rf"\b{w}\b", q) for w in ["add", "insert", "naya", "nayi"]) or any(w in question for w in ["डालो", "जोड़ो", "नया"]):

            if not available_tables:

                raise QueryGenerationError(f"Database '{db_name}' mein abhi koi table nahi hai. Pehle table banayein (e.g., create table pass_list with name, marks).")

            return parse_local_insert(clean_q, table, db_name)



        # DELETE

        if any(re.search(rf"\b{w}\b", q) for w in ["delete", "remove", "hatao", "mitao"]) or any(w in question for w in ["हटाओ", "मिटाओ"]):

            pk_col = "teacher_id" if table == "teachers" else ("department_id" if table == "departments" else ("student_id" if table == "students" else "id"))

            id_m = re.search(r"\bid\s*(?:is|=|:)?\s*(\d+)\b", q) or re.search(r"\b(\d+)\b", q)

            if id_m:

                return f"DELETE FROM {table} WHERE {pk_col} = {id_m.group(1)}"

            q_name = extract_quoted_value(clean_q)

            if not q_name:

                m = re.search(rf"(?:student|teacher|department|course|{re.escape(table)})\s+([A-Za-z\u0900-\u097F][A-Za-z\u0900-\u097F\s]{{1,40}})$", clean_q, re.I)

                if m:

                    q_name = m.group(1).strip()

            if q_name:

                q_name = transliterate_hindi(q_name)

                col_n = "department_name" if table == "departments" else ("course_name" if table == "courses" else "name")

                return f"DELETE FROM {table} WHERE LOWER({col_n}) LIKE '%{sql_str(q_name.lower())}%'"

            raise QueryGenerationError("Delete karne ke liye exact ID ya naam likhein (e.g., delete student id 2).")



        # SELECT

        if not available_tables:

            return "SHOW TABLES"



        if "average" in q or "avg" in q or "औसत" in question:

            return f"SELECT ROUND(AVG(marks), 2) AS average_marks FROM {table}"



        if "count" in q or "kitne" in q or "कितने" in question:

            return f"SELECT COUNT(*) AS total_{table} FROM {table}"



        if "top" in q or "highest" in q:

            return f"SELECT * FROM {table} ORDER BY marks DESC LIMIT 5"



        return f"SELECT * FROM {table}"

'''



# 10. app/services/sql_validator.py (HOD = Full SQL & DBs | Teacher = ONLY students table | Student = Read-Only)

FILES["app/services/sql_validator.py"] = r'''import re

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

'''



# 11. app/services/query_executor.py (Executes Meta-DB cmds + Any SQLite SQL cleanly)

FILES["app/services/query_executor.py"] = r'''import os

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

'''



# 12. app/api/routes.py

FILES["app/api/routes.py"] = r'''import time

from fastapi import APIRouter, HTTPException, Query

from app.schemas.request_models import CreateDatabaseRequest, QueryRequest, QueryResponse, SchemaResponse

from app.services.classifier import HybridClassifier

from app.services.db_manager import DBManager, DBManagerError

from app.services.llm_service import LLMService, QueryGenerationError

from app.services.schema_service import SchemaService

from app.services.sql_validator import SQLValidator, SQLValidationError

from app.services.query_executor import QueryExecutor



router = APIRouter()

llm_service = LLMService()



@router.get("/health")

def health():

    return {"status": "ok", "databases": DBManager.list_databases()}



@router.get("/databases")

def get_databases():

    return {"databases": DBManager.list_databases()}



@router.post("/databases")

def create_database(req: CreateDatabaseRequest):

    if req.role.lower() != "hod":

        raise HTTPException(status_code=403, detail="Sirf HOD hi naya database create kar sakta hai.")

    try:

        created = DBManager.create_database(req.name)

        return {"created": created, "databases": DBManager.list_databases()}

    except DBManagerError as de:

        raise HTTPException(status_code=400, detail=str(de))



@router.get("/schema", response_model=SchemaResponse)

def get_schema(

    database: str = Query("college"),

    role: str = Query("student")

):

    role_low = role.lower()

    if role_low == "teacher":

        database = "college"

    try:

        tables = SchemaService.get_live_schema(db_name=database, role=role_low)

    except DBManagerError as de:

        raise HTTPException(status_code=400, detail=str(de))

    return SchemaResponse(

        database=database,

        databases=DBManager.list_databases() if role_low != "teacher" else ["college"],

        tables=tables

    )



@router.post("/query", response_model=QueryResponse)

def run_query(req: QueryRequest):

    t0 = time.perf_counter()

    role = req.role.lower()

    db_name = req.database.strip() or "college"



    if role not in {"student", "teacher", "hod"}:

        raise HTTPException(status_code=400, detail="Invalid role. Choose student, teacher, or hod.")



    if role == "teacher" and db_name != "college":

        raise HTTPException(status_code=403, detail="Permission Denied: Teacher sirf 'college' database ki 'students' table access kar sakta hai.")



    if req.mode == "sql":

        if role == "student":

            raise HTTPException(status_code=403, detail="Direct SQL Students ke liye allowed nahi hai.")

        raw_sql = req.question.strip()

        classification_source = "DIRECT_SQL"

        intent = "direct_sql_execution"

        complexity = "direct"

        requires_join = False

        t_gen = 0.0

    else:

        classification = HybridClassifier.evaluate_rules(req.question, role=role)

        if classification.intent == "student_modification_blocked":

            raise HTTPException(

                status_code=403,

                detail="Action blocked: Students have Read-Only access. Teacher ya HOD mode switch karein."

            )



        t_gen_start = time.perf_counter()

        try:

            raw_sql = llm_service.generate_sql(req.question, classification, role=role, db_name=db_name)

        except QueryGenerationError as ge:

            raise HTTPException(status_code=400, detail=str(ge))

        except Exception as e:

            raise HTTPException(status_code=500, detail=f"AI/NLP generation error: {str(e)}")



        t_gen = round((time.perf_counter() - t_gen_start) * 1000, 2)

        classification_source = "LLM_API" if not llm_service.is_mock else classification.source

        intent = classification.intent

        complexity = classification.complexity

        requires_join = classification.requires_join



    try:

        validated_sql, action_type = SQLValidator.validate_and_format(raw_sql, role=role, db_name=db_name)

    except SQLValidationError as ve:

        raise HTTPException(status_code=403 if "Permission Denied" in str(ve) else 400, detail=str(ve))



    t_exec_start = time.perf_counter()

    try:

        columns, rows, message, active_db = QueryExecutor.execute(validated_sql, action_type, db_name=db_name)

    except DBManagerError as de:

        raise HTTPException(status_code=400, detail=str(de))

    except Exception as e:

        raise HTTPException(status_code=500, detail=f"SQLite execution error: {str(e)}")



    t_exec = round((time.perf_counter() - t_exec_start) * 1000, 2)

    total_ms = round((time.perf_counter() - t0) * 1000, 2)



    return QueryResponse(

        question=req.question,

        intent=intent,

        complexity=complexity,

        requires_join=requires_join,

        classification_source=classification_source,

        sql=validated_sql,

        action_type=action_type,

        active_database=active_db,

        databases=DBManager.list_databases() if role != "teacher" else ["college"],

        columns=columns,

        rows=rows,

        row_count=len(rows),

        message=message,

        status="success",

        generation_ms=t_gen,

        execution_ms=t_exec,

        total_ms=total_ms

    )

'''



# 13. app/main.py

FILES["app/main.py"] = r'''import os

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from app.api.routes import router



app = FastAPI(title="QueryMind AI — Multi-Database College Console")



app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)



app.include_router(router, prefix="/api")



frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(frontend_dir):

    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

'''



# 14. frontend/index.html

FILES["frontend/index.html"] = r'''<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>QueryMind AI — Multi-DB College Console</title>

    <link rel="stylesheet" href="style.css">

    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">

</head>

<body>

    <div class="layout">

        <aside class="sidebar">

            <div class="brand">

                <div class="logo">⚡</div>

                <div>

                    <h2>QueryMind AI</h2>

                    <span class="badge" id="role-badge">Student Mode</span>

                </div>

            </div>



            <div class="role-selector-card">

                <span class="role-title">COLLEGE ROLE ACCESS:</span>

                <div class="role-toggle-group">

                    <button type="button" class="role-btn active" id="btn-role-student">

                        🎓 Student<br><small>Read Only</small>

                    </button>

                    <button type="button" class="role-btn" id="btn-role-teacher">

                        👨🏫 Teacher<br><small>Students Only</small>

                    </button>

                    <button type="button" class="role-btn" id="btn-role-hod">

                        🏛️ HOD<br><small>Full SQL + DBs</small>

                    </button>

                </div>

            </div>



            <div class="db-selector-card" id="db-selector-card">

                <div class="db-card-head">

                    <span class="role-title" style="margin:0;">ACTIVE DATABASE:</span>

                    <button type="button" id="new-db-btn" class="btn-mini hod-only hidden" title="Create New Database">+ New DB</button>

                </div>

                <select id="db-selector" class="db-select">

                    <option value="college">college.db</option>

                </select>

            </div>



            <div class="sidebar-section">

                <div class="schema-header">

                    <h3 id="schema-title">Schema (college.db)</h3>

                    <button id="refresh-schema-btn" title="Refresh Schema" class="icon-btn">🔄</button>

                </div>

                <div id="schema-viewer" class="schema-list">

                    <p class="loading-text">Loading schema...</p>

                </div>

            </div>

            <div class="sidebar-footer">

                <span class="dot" id="access-dot"></span>

                <span id="access-desc">Read-Only Enforced</span>

            </div>

        </aside>



        <main class="main-content">

            <header class="topbar">

                <div>

                    <h1>College Natural Language SQL Console</h1>

                    <p class="subtext" id="role-subtext">Viewing as Student (Read-Only: SELECT queries only).</p>

                </div>

                <div class="tags">

                    <div id="mode-selector" class="mode-toggle hidden">

                        <button type="button" class="mode-btn active" id="mode-nl">AI Prompt</button>

                        <button type="button" class="mode-btn" id="mode-sql">Direct SQL</button>

                    </div>

                    <span class="badge secondary" id="active-db-pill">DB: college</span>

                </div>

            </header>



            <section class="prompt-box">

                <form id="query-form">

                    <div class="input-row">

                        <textarea id="question-input" rows="2" placeholder="Ask in English, Hindi, or Hinglish..." required></textarea>

                        <button type="submit" id="submit-btn">

                            <span id="btn-text">Execute</span>

                            <span id="btn-spinner" class="spinner hidden"></span>

                        </button>

                    </div>

                </form>



                <div class="chips" id="chips-container">

                    <span>Examples:</span>

                    <button class="chip" data-q="show all students">Show All Students</button>

                    <button class="chip write-only hidden" data-q='add student "Prem Prajapati" marks 92.5'>Add Student</button>

                    <button class="chip write-only hidden" data-q='Prem Prajapati ke marks 96 kar do'>Update Marks</button>

                    <button class="chip hod-only hidden" data-q="Create new database PassStudent">Create DB: PassStudent</button>

                    <button class="chip hod-only hidden" data-q="show databases">Show All Databases</button>

                    <button class="chip hod-only hidden" data-q="create table toppers with name, marks">Create Table</button>

                </div>

            </section>



            <div id="error-alert" class="alert hidden"></div>

            <div id="success-banner" class="success-banner hidden"></div>



            <section id="telemetry-box" class="telemetry-bar hidden">

                <div class="t-item"><span class="t-lbl">Role</span><span id="t-role" class="t-val pill">STUDENT</span></div>

                <div class="t-item"><span class="t-lbl">Database</span><span id="t-db" class="t-val pill">college</span></div>

                <div class="t-item"><span class="t-lbl">Action</span><span id="t-action" class="t-val pill">-</span></div>

                <div class="t-item"><span class="t-lbl">Engine</span><span id="t-src" class="t-val pill">-</span></div>

                <div class="t-item"><span class="t-lbl">Exec Time</span><span id="t-exec" class="t-val">0ms</span></div>

                <div class="t-spacer"></div>

                <button type="button" id="toggle-sql-btn" class="btn-sql-toggle">👁️ View SQL</button>

            </section>



            <section id="sql-panel" class="card hidden">

                <div class="card-head">

                    <span id="sql-label">Generated SQLite Query Preview</span>

                    <button id="copy-btn" class="btn-sm">Copy</button>

                </div>

                <pre><code id="sql-view"></code></pre>

            </section>



            <section id="results-panel" class="card hidden">

                <div class="card-head">

                    <div class="head-left">

                        <span id="result-title">Fetched Result</span>

                        <span id="row-badge" class="badge">0 rows</span>

                    </div>

                    <div class="head-actions">

                        <button type="button" id="export-csv-btn" class="btn-sm">⬇ Export CSV</button>

                        <button type="button" id="export-json-btn" class="btn-sm">⬇ Export JSON</button>

                    </div>

                </div>

                <div class="table-wrap">

                    <table id="data-table">

                        <thead id="tbl-head"></thead>

                        <tbody id="tbl-body"></tbody>

                    </table>

                </div>

            </section>

        </main>

    </div>

    <script src="script.js"></script>

</body>

</html>

'''



# 15. frontend/style.css

FILES["frontend/style.css"] = r'''* { box-sizing: border-box; margin: 0; padding: 0; }

body {

    background-color: #0b0f19;

    color: #f1f5f9;

    font-family: 'Plus Jakarta Sans', sans-serif;

    height: 100vh;

    overflow: hidden;

}

.layout { display: flex; height: 100vh; }

.sidebar {

    width: 340px;

    background: #111827;

    border-right: 1px solid #1f2937;

    padding: 20px;

    display: flex;

    flex-direction: column;

    gap: 14px;

}

.brand { display: flex; align-items: center; gap: 12px; }

.logo {

    width: 38px; height: 38px;

    background: rgba(56, 189, 248, 0.1);

    border: 1px solid #38bdf8;

    color: #38bdf8;

    display: flex; align-items: center; justify-content: center;

    border-radius: 8px; font-weight: bold;

}

.badge {

    background: rgba(56, 189, 248, 0.15);

    border: 1px solid #38bdf8;

    color: #38bdf8;

    font-size: 0.7rem;

    padding: 2px 6px; border-radius: 4px;

}

.badge.secondary {

    background: #1f2937; border-color: #374151; color: #38bdf8;

}



.role-selector-card, .db-selector-card {

    background: #162032;

    border: 1px solid #26334d;

    border-radius: 8px;

    padding: 10px;

}

.db-card-head {

    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 6px;

}

.db-select {

    width: 100%;

    background: #0f172a;

    color: #f1f5f9;

    border: 1px solid #334155;

    border-radius: 6px;

    padding: 7px 10px;

    font-family: 'JetBrains Mono', monospace;

    font-size: 0.8rem;

    outline: none;

}

.db-select:focus { border-color: #38bdf8; }

.btn-mini {

    background: rgba(245, 158, 11, 0.15);

    border: 1px solid #f59e0b;

    color: #f59e0b;

    padding: 2px 8px;

    border-radius: 4px;

    font-size: 0.68rem;

    font-weight: 700;

    cursor: pointer;

}

.btn-mini:hover { background: rgba(245, 158, 11, 0.3); }



.role-title {

    display: block;

    font-size: 0.65rem;

    color: #94a3b8;

    font-weight: 700;

    margin-bottom: 8px;

}

.role-toggle-group { display: flex; gap: 6px; }

.role-btn {

    flex: 1;

    background: #0f172a;

    border: 1px solid #334155;

    color: #94a3b8;

    padding: 8px 4px;

    border-radius: 6px;

    cursor: pointer;

    font-size: 0.72rem;

    font-weight: 600;

    text-align: center;

    transition: all 0.2s;

}

.role-btn small { font-weight: 400; opacity: 0.75; font-size: 0.62rem; }

.role-btn.active {

    background: rgba(56, 189, 248, 0.15);

    border-color: #38bdf8;

    color: #38bdf8;

}

.role-btn.active-teacher {

    background: rgba(16, 185, 129, 0.15);

    border-color: #10b981;

    color: #34d399;

}

.role-btn.active-hod {

    background: rgba(245, 158, 11, 0.15);

    border-color: #f59e0b;

    color: #f59e0b;

}



.sidebar-section { flex: 1; overflow-y: auto; }

.schema-header {

    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 10px;

}

.schema-header h3 { font-size: 0.75rem; text-transform: uppercase; color: #9ca3af; }

.icon-btn { background: transparent; border: none; cursor: pointer; font-size: 0.9rem; }

.tbl-card {

    background: #1f2937; border: 1px solid #374151;

    border-radius: 6px; padding: 10px; margin-bottom: 10px;

}

.tbl-card h4 { color: #38bdf8; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }

.tbl-card ul { list-style: none; padding-left: 6px; margin-top: 6px; font-size: 0.75rem; color: #9ca3af; }

.sidebar-footer { font-size: 0.75rem; color: #9ca3af; display: flex; align-items: center; gap: 8px; }

.dot { width: 8px; height: 8px; background: #38bdf8; border-radius: 50%; box-shadow: 0 0 6px #38bdf8; }

.dot.teacher { background: #10b981; box-shadow: 0 0 6px #10b981; }

.dot.hod { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }



.main-content {

    flex: 1; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;

}

.topbar { display: flex; justify-content: space-between; align-items: center; }

.topbar h1 { font-size: 1.4rem; font-weight: 700; }

.subtext { font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }

.tags { display: flex; align-items: center; gap: 10px; }



.mode-toggle { display: flex; background: #1f2937; border-radius: 6px; padding: 2px; }

.mode-btn {

    background: transparent; border: none; color: #94a3b8;

    padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; cursor: pointer; font-weight: 600;

}

.mode-btn.active { background: #38bdf8; color: #041421; }



.prompt-box {

    background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 16px;

}

.input-row { display: flex; gap: 12px; }

textarea {

    flex: 1; background: #0b0f19; border: 1px solid #374151; border-radius: 8px;

    padding: 12px; color: #fff; font-family: inherit; font-size: 0.95rem; resize: none; outline: none;

}

textarea:focus { border-color: #38bdf8; }

button#submit-btn {

    background: #38bdf8; color: #082f49; font-weight: 700; border: none; border-radius: 8px;

    padding: 0 24px; cursor: pointer; transition: opacity 0.2s;

}

button#submit-btn:hover { opacity: 0.9; }



.chips { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 0.8rem; color: #9ca3af; flex-wrap: wrap; }

.chip {

    background: #1f2937; border: 1px solid #374151; color: #e5e7eb; padding: 4px 10px;

    border-radius: 14px; cursor: pointer; font-size: 0.75rem;

}

.chip:hover { border-color: #38bdf8; }



.telemetry-bar {

    display: flex; align-items: center; gap: 18px; background: #111827; border: 1px solid #1f2937;

    border-radius: 8px; padding: 10px 16px;

}

.t-item { display: flex; flex-direction: column; gap: 2px; }

.t-lbl { font-size: 0.65rem; color: #9ca3af; text-transform: uppercase; }

.t-val { font-size: 0.85rem; font-weight: 600; }

.t-spacer { flex: 1; }

.pill { background: #1f2937; padding: 2px 8px; border-radius: 4px; color: #38bdf8; font-family: 'JetBrains Mono', monospace; }



.btn-sql-toggle {

    background: #1e293b; border: 1px solid #38bdf8; color: #38bdf8;

    padding: 6px 12px; border-radius: 6px; font-size: 0.78rem; font-weight: 600; cursor: pointer;

}

.btn-sql-toggle:hover { background: rgba(56, 189, 248, 0.15); }



.card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; overflow: hidden; }

.card-head {

    background: #162032; padding: 10px 16px; display: flex; justify-content: space-between;

    align-items: center; font-size: 0.85rem; font-weight: 600;

}

.head-left { display: flex; align-items: center; gap: 10px; }

.head-actions { display: flex; gap: 8px; }

.btn-sm { background: #0f172a; border: 1px solid #374151; color: #e2e8f0; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.75rem; }

.btn-sm:hover { border-color: #38bdf8; color: #38bdf8; }



pre { padding: 16px; font-family: 'JetBrains Mono', monospace; color: #38bdf8; font-size: 0.88rem; overflow-x: auto; }

.table-wrap { overflow-x: auto; max-height: 360px; }

table { width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; }

th, td { padding: 10px 16px; border-bottom: 1px solid #1f2937; }

th { background: #162032; color: #38bdf8; font-weight: 600; position: sticky; top: 0; }

tr:hover { background: rgba(255,255,255,0.02); }



.alert {

    background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; color: #f87171;

    padding: 12px; border-radius: 8px; font-size: 0.85rem;

}

.success-banner {

    background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; color: #34d399;

    padding: 12px; border-radius: 8px; font-size: 0.85rem;

}

.hidden { display: none !important; }

.spinner {

    display: inline-block; width: 16px; height: 16px;

    border: 2px solid rgba(0,0,0,0.2); border-top-color: #000; border-radius: 50%;

    animation: spin 0.6s linear infinite;

}

@keyframes spin { to { transform: rotate(360deg); } }

'''



# 16. frontend/script.js

FILES["frontend/script.js"] = r'''const API = "/api";

let currentRole = "student";

let currentMode = "nl";

let currentDatabase = "college";

let lastColumns = [];

let lastRows = [];

let sqlVisible = false;



document.addEventListener("DOMContentLoaded", () => {

    fetchSchema();

    setupEvents();

});



function setupEvents() {

    const form = document.getElementById("query-form");

    const input = document.getElementById("question-input");

    const btnStudent = document.getElementById("btn-role-student");

    const btnTeacher = document.getElementById("btn-role-teacher");

    const btnHod = document.getElementById("btn-role-hod");

    const modeSelector = document.getElementById("mode-selector");

    const modeNL = document.getElementById("mode-nl");

    const modeSQL = document.getElementById("mode-sql");

    const roleBadge = document.getElementById("role-badge");

    const roleSubtext = document.getElementById("role-subtext");

    const accessDot = document.getElementById("access-dot");

    const accessDesc = document.getElementById("access-desc");

    const toggleSqlBtn = document.getElementById("toggle-sql-btn");

    const dbSelector = document.getElementById("db-selector");

    const dbCard = document.getElementById("db-selector-card");

    const newDbBtn = document.getElementById("new-db-btn");



    function updateRoleUI(role) {

        currentRole = role;

        btnStudent.classList.remove("active");

        btnTeacher.classList.remove("active-teacher");

        btnHod.classList.remove("active-hod");



        if (role === "student") {

            btnStudent.classList.add("active");

            modeSelector.classList.add("hidden");

            dbCard.classList.remove("hidden");

            dbSelector.disabled = false;

            document.querySelectorAll(".write-only, .hod-only").forEach(el => el.classList.add("hidden"));

            roleBadge.textContent = "Student Mode";

            roleBadge.style.color = "#38bdf8";

            roleBadge.style.borderColor = "#38bdf8";

            roleSubtext.textContent = "Viewing as Student (Read-Only: SELECT queries only).";

            accessDot.className = "dot";

            accessDesc.textContent = "Read-Only Enforced";

            setMode("nl");

        } else if (role === "teacher") {

            btnTeacher.classList.add("active-teacher");

            modeSelector.classList.remove("hidden");

            currentDatabase = "college";

            dbSelector.value = "college";

            dbSelector.disabled = true;

            document.getElementById("active-db-pill").textContent = "DB: college";

            document.querySelectorAll(".write-only").forEach(el => el.classList.remove("hidden"));

            document.querySelectorAll(".hod-only").forEach(el => el.classList.add("hidden"));

            roleBadge.textContent = "Teacher Mode";

            roleBadge.style.color = "#34d399";

            roleBadge.style.borderColor = "#10b981";

            roleSubtext.textContent = "Teacher Access: Strictly 'students' table only (Read & Write).";

            accessDot.className = "dot teacher";

            accessDesc.textContent = "Students Table Only";

        } else {

            btnHod.classList.add("active-hod");

            modeSelector.classList.remove("hidden");

            dbCard.classList.remove("hidden");

            dbSelector.disabled = false;

            document.querySelectorAll(".write-only, .hod-only").forEach(el => el.classList.remove("hidden"));

            roleBadge.textContent = "HOD (Full Access)";

            roleBadge.style.color = "#f59e0b";

            roleBadge.style.borderColor = "#f59e0b";

            roleSubtext.textContent = "HOD Full Control: Create Databases, Tables, Insert, Update, Delete, Select & Direct SQL.";

            accessDot.className = "dot hod";

            accessDesc.textContent = "Full HOD Access";

        }

        fetchSchema();

    }



    btnStudent.addEventListener("click", () => updateRoleUI("student"));

    btnTeacher.addEventListener("click", () => updateRoleUI("teacher"));

    btnHod.addEventListener("click", () => updateRoleUI("hod"));



    dbSelector.addEventListener("change", () => {

        currentDatabase = dbSelector.value;

        document.getElementById("active-db-pill").textContent = `DB: ${currentDatabase}`;

        fetchSchema();

    });



    newDbBtn.addEventListener("click", async () => {

        const dbName = prompt("Naya database ka naam likhein (e.g. PassStudent):");

        if (!dbName || !dbName.trim()) return;

        await runQuery(`Create new database ${dbName.trim()}`);

    });



    modeNL.addEventListener("click", () => setMode("nl"));

    modeSQL.addEventListener("click", () => setMode("sql"));



    function setMode(mode) {

        currentMode = mode;

        if (mode === "nl") {

            modeNL.classList.add("active");

            modeSQL.classList.remove("active");

            input.placeholder = currentRole === "hod"

                ? "HOD Prompt: e.g., 'Create new database PassStudent', 'create table toppers with name, marks', or any query..."

                : (currentRole === "teacher"

                    ? "Teacher Prompt (Students only): e.g., 'show all students' or 'add student \"Rahul\" marks 90'..."

                    : "Student Prompt (Read-Only): e.g., 'show all students'...");

        } else {

            modeSQL.classList.add("active");

            modeNL.classList.remove("active");

            input.placeholder = "Direct SQL: e.g., CREATE DATABASE PassStudent; or CREATE TABLE ... or SELECT * FROM ...";

        }

    }



    toggleSqlBtn.addEventListener("click", () => {

        sqlVisible = !sqlVisible;

        const sqlPanel = document.getElementById("sql-panel");

        if (sqlVisible) {

            sqlPanel.classList.remove("hidden");

            toggleSqlBtn.textContent = "🙈 Hide SQL";

        } else {

            sqlPanel.classList.add("hidden");

            toggleSqlBtn.textContent = "👁️ View SQL";

        }

    });



    form.addEventListener("submit", (e) => {

        e.preventDefault();

        const q = input.value.trim();

        if (q) runQuery(q);

    });



    document.querySelectorAll(".chip").forEach(c => {

        c.addEventListener("click", () => {

            input.value = c.dataset.q;

            runQuery(c.dataset.q);

        });

    });



    document.getElementById("copy-btn").addEventListener("click", () => {

        navigator.clipboard.writeText(document.getElementById("sql-view").textContent);

        const b = document.getElementById("copy-btn");

        b.textContent = "Copied!";

        setTimeout(() => b.textContent = "Copy", 1500);

    });



    document.getElementById("export-csv-btn").addEventListener("click", exportCSV);

    document.getElementById("export-json-btn").addEventListener("click", exportJSON);

    document.getElementById("refresh-schema-btn").addEventListener("click", fetchSchema);

}



function updateDatabaseDropdown(databases, activeDb) {

    const dbSelector = document.getElementById("db-selector");

    currentDatabase = activeDb;

    dbSelector.innerHTML = "";

    databases.forEach(db => {

        const opt = document.createElement("option");

        opt.value = db;

        opt.textContent = `${db}.db`;

        if (db === activeDb) opt.selected = true;

        dbSelector.appendChild(opt);

    });

    document.getElementById("active-db-pill").textContent = `DB: ${activeDb}`;

    document.getElementById("schema-title").textContent = `Schema (${activeDb}.db)`;

}



async function fetchSchema() {

    try {

        const res = await fetch(`${API}/schema?database=${encodeURIComponent(currentDatabase)}&role=${encodeURIComponent(currentRole)}`);

        const data = await res.json();

        updateDatabaseDropdown(data.databases, data.database);



        const box = document.getElementById("schema-viewer");

        box.innerHTML = "";

        if (!data.tables || data.tables.length === 0) {

            box.innerHTML = `<p style="font-size:0.78rem; color:#94a3b8; padding:8px;">'${data.database}.db' mein abhi koi table nahi hai. HOD mode mein table create karein.</p>`;

            return;

        }

        data.tables.forEach(t => {

            const card = document.createElement("div");

            card.className = "tbl-card";

            const cols = t.columns.map(c => `<li>${c.name} <span style="opacity:0.4">${c.type}</span></li>`).join("");

            card.innerHTML = `<h4>${t.table_name}</h4><ul>${cols}</ul>`;

            box.appendChild(card);

        });

    } catch (e) {

        document.getElementById("schema-viewer").innerHTML = "<p style='color:#f87171'>Schema load error</p>";

    }

}



async function runQuery(question) {

    const btn = document.getElementById("submit-btn");

    const txt = document.getElementById("btn-text");

    const spin = document.getElementById("btn-spinner");

    const err = document.getElementById("error-alert");

    const successBanner = document.getElementById("success-banner");



    btn.disabled = true;

    txt.classList.add("hidden");

    spin.classList.remove("hidden");

    err.classList.add("hidden");

    successBanner.classList.add("hidden");



    try {

        const res = await fetch(`${API}/query`, {

            method: "POST",

            headers: { "Content-Type": "application/json" },

            body: JSON.stringify({

                question: question,

                role: currentRole,

                mode: currentMode,

                database: currentDatabase

            })

        });



        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Query rejected");



        if (data.active_database) {

            updateDatabaseDropdown(data.databases, data.active_database);

        }



        document.getElementById("t-role").textContent = currentRole.toUpperCase();

        document.getElementById("t-db").textContent = data.active_database;

        document.getElementById("t-action").textContent = data.action_type.toUpperCase();

        document.getElementById("t-src").textContent = data.classification_source.toUpperCase();

        document.getElementById("t-exec").textContent = `${data.execution_ms}ms`;

        document.getElementById("telemetry-box").classList.remove("hidden");



        document.getElementById("sql-view").textContent = data.sql;

        if (sqlVisible) {

            document.getElementById("sql-panel").classList.remove("hidden");

        } else {

            document.getElementById("sql-panel").classList.add("hidden");

        }



        if (data.message) {

            successBanner.textContent = data.message;

            successBanner.classList.remove("hidden");

        }



        if (data.action_type !== "select") {

            fetchSchema();

        }



        lastColumns = data.columns;

        lastRows = data.rows;

        renderTable(data.columns, data.rows);

        document.getElementById("row-badge").textContent = `${data.row_count} rows`;

        document.getElementById("results-panel").classList.remove("hidden");



    } catch (e) {

        err.textContent = e.message;

        err.classList.remove("hidden");

        document.getElementById("telemetry-box").classList.add("hidden");

        document.getElementById("sql-panel").classList.add("hidden");

        document.getElementById("results-panel").classList.add("hidden");

    } finally {

        btn.disabled = false;

        txt.classList.remove("hidden");

        spin.classList.add("hidden");

    }

}



function renderTable(cols, rows) {

    const head = document.getElementById("tbl-head");

    const body = document.getElementById("tbl-body");

    head.innerHTML = "";

    body.innerHTML = "";



    if (!cols || cols.length === 0) {

        body.innerHTML = `<tr><td style="text-align:center; color:#9ca3af;">Operation completed.</td></tr>`;

        return;

    }



    const tr = document.createElement("tr");

    cols.forEach(c => {

        const th = document.createElement("th");

        th.textContent = c.toUpperCase();

        tr.appendChild(th);

    });

    head.appendChild(tr);



    if (rows.length === 0) {

        body.innerHTML = `<tr><td colspan="${cols.length}" style="text-align:center; color:#9ca3af;">No records yet.</td></tr>`;

        return;

    }



    rows.forEach(r => {

        const row = document.createElement("tr");

        cols.forEach(c => {

            const td = document.createElement("td");

            td.textContent = r[c] !== null && r[c] !== undefined ? r[c] : "NULL";

            row.appendChild(td);

        });

        body.appendChild(row);

    });

}



function downloadFile(content, filename, mimeType) {

    const blob = new Blob([content], { type: mimeType });

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");

    a.href = url;

    a.download = filename;

    document.body.appendChild(a);

    a.click();

    document.body.removeChild(a);

    URL.revokeObjectURL(url);

}



function exportCSV() {

    if (!lastColumns.length) return;

    const escapeCSV = (val) => {

        if (val === null || val === undefined) return "";

        const s = String(val);

        return s.includes(",") || s.includes('"') || s.includes("\n")

            ? '"' + s.replace(/"/g, '""') + '"'

            : s;

    };

    const lines = [lastColumns.join(",")];

    lastRows.forEach(r => {

        lines.push(lastColumns.map(c => escapeCSV(r[c])).join(","));

    });

    downloadFile(lines.join("\n"), `${currentDatabase}_export_${Date.now()}.csv`, "text/csv;charset=utf-8;");

}



function exportJSON() {

    if (!lastColumns.length) return;

    downloadFile(JSON.stringify(lastRows, null, 2), `${currentDatabase}_export_${Date.now()}.json`, "application/json");

}

'''



# 17. run.py

FILES["run.py"] = '''import uvicorn

import webbrowser

import threading

import time

from init_db import init_database

from app.config import settings



def open_browser():

    time.sleep(1.5)

    url = f"http://{settings.HOST}:{settings.PORT}"

    print(f"\\n[+] Opening browser at: {url}")

    webbrowser.open(url)



if __name__ == "__main__":

    print("[*] Checking/Initializing SQLite Database (college.db)...")

    init_database()

    threading.Thread(target=open_browser, daemon=True).start()

    print(f"[*] Starting QueryMind AI Server on http://{settings.HOST}:{settings.PORT} ...")

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)

'''



def build():

    print("=" * 60)

    print(" [*] QueryMind AI: Multi-DB HOD + Strict Teacher Engine")

    print("=" * 60)



    for rel_path, content in FILES.items():

        dir_name = os.path.dirname(rel_path)

        if dir_name and not os.path.exists(dir_name):

            os.makedirs(dir_name, exist_ok=True)

        with open(rel_path, "w", encoding="utf-8") as f:

            f.write(content.strip() + "\n")

        print(f"  [OK] Generated: {rel_path}")



    print("\n[SUCCESS] Build complete!")

    print("=" * 60)

    print("Run karein:  python run.py")

    print("=" * 60)



if __name__ == "__main__":

    build()
