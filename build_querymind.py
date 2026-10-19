import os

FILES = {}

# 1. requirements.txt
FILES["requirements.txt"] = """fastapi>=0.110.0
uvicorn[standard]>=0.28.0
sqlalchemy>=2.0.28
sqlglot>=23.0.0
pydantic>=2.6.0
pydantic-settings>=2.2.1
openai>=1.14.0
httpx>=0.27.0
"""

# 2. .env
FILES[".env"] = """APP_ENV=development
HOST=127.0.0.1
PORT=8000
DATABASE_URL=sqlite:///./college.db
LLM_API_KEY=mock-key-development
LLM_MODEL=gpt-4o-mini
MAX_RESULT_ROWS=200
QUERY_TIMEOUT_SECONDS=5
"""

# 3. init_db.py
FILES["init_db.py"] = '''from sqlalchemy import create_engine, text
from app.config import settings

def seed_database():
    engine = create_engine(settings.DATABASE_URL)
    is_sqlite = "sqlite" in settings.DATABASE_URL.lower()
    
    with engine.begin() as conn:
        if is_sqlite:
            conn.execute(text("DROP TABLE IF EXISTS enrollments;"))
            conn.execute(text("DROP TABLE IF EXISTS courses;"))
            conn.execute(text("DROP TABLE IF EXISTS students;"))
            conn.execute(text("DROP TABLE IF EXISTS departments;"))
        else:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            conn.execute(text("DROP TABLE IF EXISTS enrollments;"))
            conn.execute(text("DROP TABLE IF EXISTS courses;"))
            conn.execute(text("DROP TABLE IF EXISTS students;"))
            conn.execute(text("DROP TABLE IF EXISTS departments;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

        conn.execute(text("""
            CREATE TABLE departments (
                department_id INTEGER PRIMARY KEY,
                department_name VARCHAR(100) NOT NULL
            );
        """))

        conn.execute(text("""
            CREATE TABLE students (
                student_id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                department_id INTEGER NOT NULL,
                marks REAL,
                FOREIGN KEY (department_id) REFERENCES departments(department_id)
            );
        """))

        conn.execute(text("""
            CREATE TABLE courses (
                course_id INTEGER PRIMARY KEY,
                course_name VARCHAR(100) NOT NULL,
                department_id INTEGER NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(department_id)
            );
        """))

        conn.execute(text("""
            CREATE TABLE enrollments (
                enrollment_id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                grade VARCHAR(5),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (course_id) REFERENCES courses(course_id)
            );
        """))

        conn.execute(text("""
            INSERT INTO departments VALUES
            (1, 'Computer Science'),
            (2, 'Data Science'),
            (3, 'Mechanical Engineering'),
            (4, 'Electrical Engineering');
        """))

        conn.execute(text("""
            INSERT INTO students VALUES
            (101, 'Aarav Sharma', 1, 91.50),
            (102, 'Priya Patel', 1, 88.00),
            (103, 'Rohan Verma', 2, 74.20),
            (104, 'Ananya Iyer', 2, 95.80),
            (105, 'Karan Malhotra', 3, 62.00),
            (106, 'Sneha Reddy', 4, 83.50),
            (107, 'Vikram Das', 1, 69.40),
            (108, 'Neha Joshi', 3, 78.10);
        """))

        conn.execute(text("""
            INSERT INTO courses VALUES
            (201, 'Data Structures & Algorithms', 1),
            (202, 'Machine Learning', 2),
            (203, 'Thermodynamics', 3),
            (204, 'Digital Signal Processing', 4),
            (205, 'Database Management Systems', 1);
        """))

        conn.execute(text("""
            INSERT INTO enrollments VALUES
            (1, 101, 201, 'A+'),
            (2, 101, 205, 'A'),
            (3, 102, 201, 'A'),
            (4, 103, 202, 'B'),
            (5, 104, 202, 'A+'),
            (6, 105, 203, 'C'),
            (7, 106, 204, 'A'),
            (8, 108, 203, 'B+');
        """))

    print("[OK] Database setup complete with sample college records!")

if __name__ == "__main__":
    seed_database()
'''

# 4. app/config.py
FILES["app/config.py"] = '''from pydantic_settings import BaseSettings, SettingsConfigDict

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

# 5. app/schemas/request_models.py
FILES["app/schemas/request_models.py"] = '''from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    role: str = Field("student", description="'student' or 'associate'")
    mode: str = Field("nl", description="'nl' or 'sql'")

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
    tables: List[TableSchema]

class QueryResponse(BaseModel):
    question: str
    intent: str
    complexity: str
    requires_join: bool
    classification_source: str
    sql: str
    action_type: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    message: Optional[str] = None
    status: str
    generation_ms: float
    execution_ms: float
    total_ms: float
'''

# 6. app/services/schema_service.py
FILES["app/services/schema_service.py"] = '''from typing import Dict, List, Set
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
            parts.append(f"CREATE TABLE {tbl} (\\n" + ",\\n".join(cols) + "\\n);")
        return "\\n\\n".join(parts)
'''

# 7. app/services/classifier.py (Recognizes 'change', 'set', 'modify' and multi-updates)
FILES["app/services/classifier.py"] = '''from typing import Optional
from app.schemas.request_models import ClassificationResult

class HybridClassifier:
    @classmethod
    def evaluate_rules(cls, text: str, role: str = "student") -> Optional[ClassificationResult]:
        normalized = text.strip().lower()

        if "drop database" in normalized or "truncate" in normalized:
            return ClassificationResult(
                intent="unsupported_or_risky",
                complexity="high",
                requires_join=False,
                risk_level="high",
                confidence=1.0,
                source="rule",
                reasoning="Database destruction is prohibited."
            )

        # 1. ACTION / MODIFICATION takes priority if explicit change/update words exist
        mod_keywords = [
            "change", "update", "replace", "set", "modify", "badal", "badlo", "kardo", "kar do",
            "add", "insert", "naya", "nayi", "new student", "delete", "remove", "hatao", "alter"
        ]
        is_mod = any(f" {k} " in f" {normalized} " or normalized.startswith(k) for k in mod_keywords)

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
            else:
                return ClassificationResult(
                    intent="data_modification",
                    complexity="medium",
                    requires_join=False,
                    risk_level="low",
                    confidence=0.98,
                    source="rule",
                    reasoning="Modification approved for College Associate."
                )

        # 2. RETRIEVAL / SELECT
        view_keywords = ["show", "list", "display", "get", "find", "dikhao", "batao", "dekho", "select", "who", "which", "what"]
        is_read_intent = any(normalized.startswith(vw) or f" {vw} " in f" {normalized} " for vw in view_keywords)

        if is_read_intent:
            return ClassificationResult(
                intent="projection",
                complexity="simple",
                requires_join="department" in normalized and "student" in normalized,
                risk_level="low",
                confidence=0.99,
                source="rule",
                reasoning="Data retrieval query."
            )

        return None
'''

# 8. app/services/llm_service.py (Multi-Student Update & Marks-by-Name Engine)
FILES["app/services/llm_service.py"] = '''import json
from openai import OpenAI
from app.config import settings
from app.schemas.request_models import ClassificationResult
from app.services.schema_service import SchemaService

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

def get_ordinal_offset(text: str) -> int:
    lower = text.lower()
    for word in lower.replace("'", " ").replace('"', " ").split():
        for suffix in ["st", "nd", "rd", "th"]:
            if word.endswith(suffix):
                num_part = word[:-len(suffix)]
                if num_part.isdigit():
                    return max(0, int(num_part) - 1)

    words = {
        "first": 0, "pehla": 0, "pehle": 0,
        "second": 1, "doosra": 1, "dusre": 1,
        "third": 2, "teesra": 2, "teesre": 2,
        "fourth": 3, "chautha": 3,
        "fifth": 4, "panchva": 4
    }
    for w, off in words.items():
        if f" {w} " in f" {lower} ":
            return off

    return 0

def extract_replacement_name(clause: str) -> str:
    clean = clause.replace("“", '"').replace("”", '"').replace("’", "'")
    
    # 1. Quoted string
    if '"' in clean:
        parts = clean.split('"')
        for idx in range(1, len(parts), 2):
            val = parts[idx].strip()
            if val and not val.replace(".", "").isdigit():
                return transliterate_hindi(val)

    # 2. Trigger words
    triggers = ["with ", "to ", "as ", "naam ", "name "]
    lower = clean.lower()
    for tr in triggers:
        if tr in lower:
            idx = lower.find(tr) + len(tr)
            candidate = clean[idx:].strip()
            for stop in [" se", " ko", " kardo", " kar do", " please"]:
                if candidate.lower().endswith(stop):
                    candidate = candidate[:-len(stop)].strip()
            
            for ch in [".", ",", ";", ":", "'", '"']:
                candidate = candidate.strip(ch)
            candidate = candidate.strip()

            if candidate and not candidate.isdigit():
                return transliterate_hindi(candidate)

    return "Himanshu"

def parse_single_update_clause(clause: str) -> str:
    """Parses an individual update statement from a clause."""
    clean = clause.replace("“", '"').replace("”", '"').replace("’", "'")
    lower = clean.lower()

    # Sub-case A: MARKS UPDATE (e.g. "change marks of prem prajapati is 90")
    if "mark" in lower or "number" in lower or "score" in lower:
        # Extract number for marks
        marks_val = "90.0"
        tokens = clean.replace('"', ' ').replace("'", ' ').replace('=', ' ').replace(':', ' ').split()
        for tok in tokens:
            if tok.replace(".", "").isdigit() and len(tok) <= 4:
                marks_val = tok

        # Extract target student (Name, ID, or Ordinal)
        # Check if an ordinal like 3rd, 4th is used
        offset = get_ordinal_offset(lower)
        if any(suf in lower for suf in ["st", "nd", "rd", "th", "first", "second", "third", "fourth"]):
            target_subquery = f"(SELECT student_id FROM students ORDER BY student_id ASC LIMIT 1 OFFSET {offset})"
            return f"UPDATE students SET marks = {marks_val} WHERE student_id = {target_subquery}"

        # Check if 3-digit student ID is used
        for tok in tokens:
            if tok.isdigit() and len(tok) == 3:
                return f"UPDATE students SET marks = {marks_val} WHERE student_id = {tok}"

        # Check if student name is used (e.g. "marks of prem prajapati is 90")
        target_name = ""
        triggers = ["of ", "student ", "marks "]
        for tr in triggers:
            if tr in lower:
                idx = lower.find(tr) + len(tr)
                rem = clean[idx:].strip()
                # Stop at 'is', 'to', '=', 'marks', or digits
                for end_tr in [" is ", " to ", " =", " marks", " number"]:
                    if end_tr in rem.lower():
                        rem = rem[:rem.lower().find(end_tr)].strip()
                rem_clean = rem.strip(" .,;:'\\"")
                if rem_clean and not rem_clean.isdigit():
                    target_name = rem_clean
                    break

        if target_name:
            target_name = transliterate_hindi(target_name)
            # Match by name or first name
            first_word = target_name.split()[0].lower()
            return f"UPDATE students SET marks = {marks_val} WHERE LOWER(name) LIKE '%{target_name.lower()}%' OR LOWER(name) LIKE '%{first_word}%'"

        return f"UPDATE students SET marks = {marks_val} WHERE student_id = (SELECT student_id FROM students ORDER BY student_id ASC LIMIT 1)"

    # Sub-case B: NAME UPDATE
    target_name = extract_replacement_name(clean)

    # Check for ordinal (1st, 2nd, 3rd, 4th etc.)
    offset = get_ordinal_offset(lower)
    target_subquery = f"(SELECT student_id FROM students ORDER BY student_id ASC LIMIT 1 OFFSET {offset})"

    # Check for specific ID
    tokens = clean.replace('"', ' ').replace("'", ' ').split()
    for tok in tokens:
        if tok.isdigit() and len(tok) == 3:
            target_subquery = tok
            break

    return f"UPDATE students SET name = '{target_name}' WHERE student_id = {target_subquery}"

class LLMService:
    def __init__(self):
        self.is_mock = "mock" in settings.LLM_API_KEY.lower() or not settings.LLM_API_KEY.startswith("sk-")
        if not self.is_mock:
            self.client = OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL
            )
        self.model = settings.LLM_MODEL

    def classify_question(self, question: str, role: str = "student") -> ClassificationResult:
        q = question.lower()
        if any(w in q for w in ["change", "update", "replace", "set", "modify", "add", "insert", "delete", "remove", "alter", "badlo"]):
            if role == "student":
                return ClassificationResult(
                    intent="student_modification_blocked",
                    complexity="medium",
                    requires_join=False,
                    risk_level="high",
                    confidence=1.0,
                    source="mock-engine",
                    reasoning="Student role is Read-Only."
                )
            return ClassificationResult(
                intent="data_modification",
                complexity="medium",
                requires_join=False,
                risk_level="low",
                confidence=0.98,
                source="mock-engine",
                reasoning="College Associate Authorized."
            )

        return ClassificationResult(
            intent="projection",
            complexity="simple",
            requires_join=False,
            risk_level="low",
            confidence=0.9,
            source="mock-engine",
            reasoning="Default view query"
        )

    def generate_sql(self, question: str, classification: ClassificationResult, role: str = "student") -> str:
        if self.is_mock:
            q = question.lower()
            clean_q = question.replace("“", '"').replace("”", '"').replace("’", "'")

            # -------------------------------------------------------------
            # CASE 1: MULTI-UPDATE / SINGLE UPDATE
            # -------------------------------------------------------------
            if any(w in q for w in ["change", "update", "replace", "set", "modify", "badal", "badlo"]):
                # Check if multiple updates are linked with " and " (e.g. 3rd student name to X and 4th student name to Y)
                if " and " in clean_q and any(suf in clean_q.lower() for suf in ["student", "marks", "name"]):
                    clauses = [c.strip() for c in clean_q.split(" and ") if c.strip()]
                    sql_statements = []
                    for clause in clauses:
                        sql_statements.append(parse_single_update_clause(clause))
                    return ";\\n".join(sql_statements)
                else:
                    return parse_single_update_clause(clean_q)

            # -------------------------------------------------------------
            # CASE 2: INSERT / ADD STUDENT
            # -------------------------------------------------------------
            if any(w in q for w in ["add", "insert", "naya", "nayi", "new"]):
                new_name = "Himanshu"
                if '"' in clean_q:
                    parts = clean_q.split('"')
                    for idx in range(1, len(parts), 2):
                        cand = parts[idx].strip()
                        if not cand.replace(".", "").isdigit():
                            new_name = cand
                            break
                new_name = transliterate_hindi(new_name)

                new_id = "(SELECT COALESCE(MAX(student_id), 100) + 1 FROM students)"
                new_dept = "1"
                new_marks = "85.0"

                tokens = clean_q.replace('"', ' ').replace("'", ' ').replace('=', ' ').replace(':', ' ').split()

                for i, tok in enumerate(tokens):
                    tok_low = tok.lower()
                    if tok_low == "id" or tok_low == "student_id":
                        is_dept = i > 0 and ("dept" in tokens[i-1].lower() or "department" in tokens[i-1].lower())
                        if is_dept and i + 1 < len(tokens) and tokens[i+1].isdigit():
                            new_dept = tokens[i+1]
                        elif not is_dept and i + 1 < len(tokens) and tokens[i+1].isdigit():
                            new_id = tokens[i+1]

                    elif "dept" in tok_low or "department" in tok_low:
                        if i + 1 < len(tokens) and tokens[i+1].isdigit():
                            new_dept = tokens[i+1]
                        elif i + 2 < len(tokens) and tokens[i+1].lower() == "id" and tokens[i+2].isdigit():
                            new_dept = tokens[i+2]

                    elif any(m in tok_low for m in ["mark", "score", "number"]):
                        if i + 1 < len(tokens):
                            val = tokens[i+1].strip()
                            if val.replace(".", "").isdigit():
                                new_marks = val

                return f"INSERT INTO students (student_id, name, department_id, marks) VALUES ({new_id}, '{new_name}', {new_dept}, {new_marks})"

            # -------------------------------------------------------------
            # CASE 3: DELETE / REMOVE
            # -------------------------------------------------------------
            if any(w in q for w in ["delete", "remove", "hatao"]):
                target_id = "108"
                for tok in clean_q.split():
                    if tok.isdigit() and len(tok) >= 3:
                        target_id = tok
                        break
                return f"DELETE FROM students WHERE student_id = {target_id}"

            # -------------------------------------------------------------
            # CASE 4: ALTER TABLE
            # -------------------------------------------------------------
            if "column" in q:
                col_name = "email"
                if "phone" in q: col_name = "phone_number"
                elif "address" in q: col_name = "address"
                return f"ALTER TABLE students ADD COLUMN {col_name} VARCHAR(100)"

            # -------------------------------------------------------------
            # CASE 5: SELECT / RETRIEVAL
            # -------------------------------------------------------------
            all_signals = ["all data", "sara data", "poora data", "all details", "everything", "all records", "all of students", "all student data"]
            is_all = any(s in q for s in all_signals) or (q.strip() in ["show students", "show all students", "list students"])

            if is_all:
                return "SELECT student_id, name, department_id, marks FROM students"

            cols = []
            if "name" in q or "naam" in q or "नाम" in question:
                cols.append("name")
            if "mark" in q or "marks" in q or "number" in q or "score" in q or "नंबर" in question:
                cols.append("marks")
            if "student id" in q or "student_id" in q or " id " in f" {q} ":
                cols.append("student_id")
            if "department" in q or "dept" in q:
                if "department name" in q:
                    return "SELECT s.name, d.department_name FROM students s JOIN departments d ON s.department_id = d.department_id"
                else:
                    cols.append("department_id")

            if not cols:
                cols = ["student_id", "name", "department_id", "marks"]

            cols_str = ", ".join(cols)

            if "top" in q or "highest" in q:
                return f"SELECT {cols_str} FROM students ORDER BY marks DESC LIMIT 5"
            if "average" in q or "avg" in q:
                return "SELECT AVG(marks) AS average_marks FROM students"
            if "count" in q and "department" in q:
                return "SELECT d.department_name, COUNT(s.student_id) AS student_count FROM departments d LEFT JOIN students s ON d.department_id = s.department_id GROUP BY d.department_name"

            return f"SELECT {cols_str} FROM students"

        # Production LLM Prompt
        ddl = SchemaService.get_ddl_representation()
        sys_prompt = f"""You are a SQL generator for a college database.
Schema:
{ddl}

Rules:
1. Support multi-statement updates separated by semicolon if requested.
2. If user requests to change marks by name (e.g. change marks of X is 90), generate an UPDATE statement.
3. Output raw SQL only."""

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
            sql = "\\n".join([line for line in sql.split("\\n") if not line.startswith("```")]).strip()
        return sql
'''

# 9. app/services/sql_validator.py (Allows Multiple Updates for Associates)
FILES["app/services/sql_validator.py"] = '''import sqlglot
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
'''

# 10. app/services/query_executor.py (Executes Single or Multiple Statements)
FILES["app/services/query_executor.py"] = '''from typing import Any, Dict, List, Tuple
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
'''

# 11. app/api/routes.py
FILES["app/api/routes.py"] = '''import time
from fastapi import APIRouter, HTTPException
from app.schemas.request_models import QueryRequest, QueryResponse, SchemaResponse
from app.services.classifier import HybridClassifier
from app.services.llm_service import LLMService
from app.services.schema_service import SchemaService
from app.services.sql_validator import SQLValidator, SQLValidationError
from app.services.query_executor import QueryExecutor

router = APIRouter()
llm_service = LLMService()

@router.get("/health")
def health():
    return {"status": "ok", "app": "QueryMind AI Engine"}

@router.get("/schema", response_model=SchemaResponse)
def get_schema():
    return SchemaResponse(tables=SchemaService.get_live_schema())

@router.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    t0 = time.perf_counter()
    role = req.role.lower()

    if req.mode == "sql":
        if role != "associate":
            raise HTTPException(status_code=403, detail="Direct SQL Execution is only permitted for College Associates.")
        raw_sql = req.question.strip()
        classification_source = "DIRECT_SQL"
        intent = "direct_sql_execution"
        complexity = "direct"
        requires_join = False
        t_gen = 0.0
    else:
        classification = HybridClassifier.evaluate_rules(req.question, role=role)
        if classification is None:
            classification = llm_service.classify_question(req.question, role=role)

        if classification.intent == "student_modification_blocked":
            raise HTTPException(
                status_code=403,
                detail="Action blocked: Students have Read-Only permissions. Please switch to College Associate mode."
            )
        if classification.intent == "unsupported_or_risky":
            raise HTTPException(status_code=400, detail="Action blocked: Dangerous system operations are forbidden.")

        t_gen_start = time.perf_counter()
        raw_sql = llm_service.generate_sql(req.question, classification, role=role)
        t_gen = round((time.perf_counter() - t_gen_start) * 1000, 2)
        classification_source = classification.source
        intent = classification.intent
        complexity = classification.complexity
        requires_join = classification.requires_join

    try:
        validated_sql, action_type = SQLValidator.validate_and_format(raw_sql, role=role)
    except SQLValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    t_exec_start = time.perf_counter()
    try:
        columns, rows, message = QueryExecutor.execute(validated_sql, action_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database execution error: {str(e)}")
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

# 12. app/main.py
FILES["app/main.py"] = '''import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router

app = FastAPI(title="QueryMind AI Console")

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

# 13. frontend/index.html
FILES["frontend/index.html"] = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QueryMind AI — Dual-Role Text-to-SQL Engine</title>
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
                <span class="role-title">CURRENT ROLE ACCESS:</span>
                <div class="role-toggle-group">
                    <button type="button" class="role-btn active" id="btn-role-student">
                        🎓 Student<br><small>Read Only</small>
                    </button>
                    <button type="button" class="role-btn" id="btn-role-associate">
                        🏛️ College Associate<br><small>Read & Write</small>
                    </button>
                </div>
            </div>

            <div class="sidebar-section">
                <div class="schema-header">
                    <h3>Permitted Schema</h3>
                    <button id="refresh-schema-btn" title="Refresh Live Database Schema" class="icon-btn">🔄</button>
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
                    <h1>Natural Language SQL Console</h1>
                    <p class="subtext" id="role-subtext">Viewing as Student (Queries are constrained to SELECT only).</p>
                </div>
                <div class="tags">
                    <div id="mode-selector" class="mode-toggle hidden">
                        <button type="button" class="mode-btn active" id="mode-nl">AI Prompt</button>
                        <button type="button" class="mode-btn" id="mode-sql">Direct SQL</button>
                    </div>
                    <span class="badge secondary">SQLGlot Guarded</span>
                </div>
            </header>

            <section class="prompt-box">
                <form id="query-form">
                    <div class="input-row">
                        <textarea id="question-input" rows="2" placeholder="Ask questions or type changes in plain English or Hindi..." required></textarea>
                        <button type="submit" id="submit-btn">
                            <span id="btn-text">Execute</span>
                            <span id="btn-spinner" class="spinner hidden"></span>
                        </button>
                    </div>
                </form>

                <div class="chips" id="chips-container">
                    <span>Try:</span>
                    <button class="chip" data-q="show all data of students">Show All Student Data</button>
                    <button class="chip" data-q="show all student name and their marks">Exact: Names & Marks</button>
                    <button class="chip associate-only hidden" data-q='replace 3rd student name to "Himanshu" and 4th student name to "Himanshu Prajapati"'>Multi-Update: 3rd & 4th Student</button>
                    <button class="chip associate-only hidden" data-q="change marks of Aarav Sharma is 99">Change Marks of Aarav to 99</button>
                    <button class="chip associate-only hidden" data-q='add new student who has name "Prem Prajapati" and student Id "115" and department id "2" marks "92.5"'>Add Prem Prajapati</button>
                </div>
            </section>

            <div id="error-alert" class="alert hidden"></div>
            <div id="success-banner" class="success-banner hidden"></div>

            <section id="telemetry-box" class="telemetry-bar hidden">
                <div class="t-item"><span class="t-lbl">Role</span><span id="t-role" class="t-val pill">STUDENT</span></div>
                <div class="t-item"><span class="t-lbl">Action</span><span id="t-action" class="t-val pill">-</span></div>
                <div class="t-item"><span class="t-lbl">Classifier</span><span id="t-src" class="t-val pill">-</span></div>
                <div class="t-item"><span class="t-lbl">Gen Time</span><span id="t-gen" class="t-val">0ms</span></div>
                <div class="t-item"><span class="t-lbl">Exec Time</span><span id="t-exec" class="t-val">0ms</span></div>
            </section>

            <section id="sql-panel" class="card hidden">
                <div class="card-head">
                    <span id="sql-label">Generated SQL Statement</span>
                    <button id="copy-btn" class="btn-sm">Copy</button>
                </div>
                <pre><code id="sql-view"></code></pre>
            </section>

            <section id="results-panel" class="card hidden">
                <div class="card-head">
                    <span id="result-title">Result Set</span>
                    <span id="row-badge" class="badge">0 rows</span>
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

# 14. frontend/style.css
FILES["frontend/style.css"] = '''* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background-color: #0b0f19;
    color: #f1f5f9;
    font-family: 'Plus Jakarta Sans', sans-serif;
    height: 100vh;
    overflow: hidden;
}
.layout { display: flex; height: 100vh; }
.sidebar {
    width: 330px;
    background: #111827;
    border-right: 1px solid #1f2937;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
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
    background: #1f2937; border-color: #374151; color: #9ca3af;
}

.role-selector-card {
    background: #162032;
    border: 1px solid #26334d;
    border-radius: 8px;
    padding: 10px;
}
.role-title {
    display: block;
    font-size: 0.65rem;
    color: #94a3b8;
    font-weight: 700;
    margin-bottom: 8px;
}
.role-toggle-group {
    display: flex;
    gap: 6px;
}
.role-btn {
    flex: 1;
    background: #0f172a;
    border: 1px solid #334155;
    color: #94a3b8;
    padding: 8px 4px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 600;
    text-align: center;
    transition: all 0.2s;
}
.role-btn small { font-weight: 400; opacity: 0.7; font-size: 0.65rem; }
.role-btn.active {
    background: rgba(56, 189, 248, 0.15);
    border-color: #38bdf8;
    color: #38bdf8;
}
.role-btn.active-admin {
    background: rgba(245, 158, 11, 0.15);
    border-color: #f59e0b;
    color: #f59e0b;
}

.sidebar-section { flex: 1; overflow-y: auto; }
.schema-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.schema-header h3 { font-size: 0.75rem; text-transform: uppercase; color: #9ca3af; }
.icon-btn {
    background: transparent; border: none; cursor: pointer; font-size: 0.9rem;
}
.tbl-card {
    background: #1f2937; border: 1px solid #374151;
    border-radius: 6px; padding: 10px; margin-bottom: 10px;
}
.tbl-card h4 { color: #38bdf8; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
.tbl-card ul { list-style: none; padding-left: 6px; margin-top: 6px; font-size: 0.75rem; color: #9ca3af; }
.sidebar-footer { font-size: 0.75rem; color: #9ca3af; display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; background: #38bdf8; border-radius: 50%; box-shadow: 0 0 6px #38bdf8; }
.dot.admin { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }

.main-content {
    flex: 1; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px;
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
    display: flex; gap: 20px; background: #111827; border: 1px solid #1f2937;
    border-radius: 8px; padding: 10px 16px;
}
.t-item { display: flex; flex-direction: column; gap: 2px; }
.t-lbl { font-size: 0.65rem; color: #9ca3af; text-transform: uppercase; }
.t-val { font-size: 0.85rem; font-weight: 600; }
.pill { background: #1f2937; padding: 2px 8px; border-radius: 4px; color: #38bdf8; font-family: 'JetBrains Mono', monospace; }

.card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; overflow: hidden; }
.card-head {
    background: #162032; padding: 10px 16px; display: flex; justify-content: space-between;
    align-items: center; font-size: 0.85rem; font-weight: 600;
}
.btn-sm { background: transparent; border: 1px solid #374151; color: #fff; padding: 4px 8px; border-radius: 4px; cursor: pointer; }
.btn-sm:hover { border-color: #38bdf8; }

pre { padding: 16px; font-family: 'JetBrains Mono', monospace; color: #38bdf8; font-size: 0.9rem; overflow-x: auto; }
.table-wrap { overflow-x: auto; max-height: 340px; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; }
th, td { padding: 10px 16px; border-bottom: 1px solid #1f2937; }
th { background: #162032; color: #38bdf8; font-weight: 600; }
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

# 15. frontend/script.js
FILES["frontend/script.js"] = '''const API = "/api";
let currentRole = "student";
let currentMode = "nl";

document.addEventListener("DOMContentLoaded", () => {
    fetchSchema();
    setupEvents();
});

function setupEvents() {
    const form = document.getElementById("query-form");
    const input = document.getElementById("question-input");
    const btnStudent = document.getElementById("btn-role-student");
    const btnAssociate = document.getElementById("btn-role-associate");
    const modeSelector = document.getElementById("mode-selector");
    const modeNL = document.getElementById("mode-nl");
    const modeSQL = document.getElementById("mode-sql");
    const roleBadge = document.getElementById("role-badge");
    const roleSubtext = document.getElementById("role-subtext");
    const accessDot = document.getElementById("access-dot");
    const accessDesc = document.getElementById("access-desc");

    btnStudent.addEventListener("click", () => {
        currentRole = "student";
        btnStudent.classList.add("active");
        btnAssociate.classList.remove("active-admin");
        modeSelector.classList.add("hidden");
        document.querySelectorAll(".associate-only").forEach(el => el.classList.add("hidden"));
        roleBadge.textContent = "Student Mode";
        roleBadge.style.color = "#38bdf8";
        roleBadge.style.borderColor = "#38bdf8";
        roleSubtext.textContent = "Viewing as Student (Queries are constrained to SELECT only).";
        accessDot.className = "dot";
        accessDesc.textContent = "Read-Only Enforced";
        input.placeholder = "Ask questions about students, departments, or marks in plain English...";
        setMode("nl");
    });

    btnAssociate.addEventListener("click", () => {
        currentRole = "associate";
        btnAssociate.classList.add("active-admin");
        btnStudent.classList.remove("active");
        modeSelector.classList.remove("hidden");
        document.querySelectorAll(".associate-only").forEach(el => el.classList.remove("hidden"));
        roleBadge.textContent = "Associate (Full Access)";
        roleBadge.style.color = "#f59e0b";
        roleBadge.style.borderColor = "#f59e0b";
        roleSubtext.textContent = "Authorized: Can Insert, Update multiple records, Delete, or Alter Schema.";
        accessDot.className = "dot admin";
        accessDesc.textContent = "Read & Write Enabled";
    });

    modeNL.addEventListener("click", () => setMode("nl"));
    modeSQL.addEventListener("click", () => setMode("sql"));

    function setMode(mode) {
        currentMode = mode;
        if (mode === "nl") {
            modeNL.classList.add("active");
            modeSQL.classList.remove("active");
            input.placeholder = currentRole === "associate" 
                ? "Type update or query (e.g. 'replace 3rd student name to Himanshu and 4th student name to Himanshu Prajapati')..."
                : "Ask questions about students or marks...";
        } else {
            modeSQL.classList.add("active");
            modeNL.classList.remove("active");
            input.placeholder = "Enter raw SQL (e.g. ALTER TABLE students ADD COLUMN email VARCHAR(100);)...";
        }
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = input.value.trim();
        if (q) runQuery(q);
    });

    document.querySelectorAll(".chip").forEach(c => {
        c.addEventListener("click", () => {
            input.value = c.dataset.q;
            if (c.dataset.q.toUpperCase().startsWith("ALTER") || c.dataset.q.toUpperCase().startsWith("INSERT")) {
                if (currentRole === "associate") setMode("sql");
            }
            runQuery(c.dataset.q);
        });
    });

    document.getElementById("copy-btn").addEventListener("click", () => {
        navigator.clipboard.writeText(document.getElementById("sql-view").textContent);
        const b = document.getElementById("copy-btn");
        b.textContent = "Copied!";
        setTimeout(() => b.textContent = "Copy", 1500);
    });

    document.getElementById("refresh-schema-btn").addEventListener("click", () => {
        fetchSchema();
    });
}

async function fetchSchema() {
    try {
        const res = await fetch(`${API}/schema`);
        const data = await res.json();
        const box = document.getElementById("schema-viewer");
        box.innerHTML = "";
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
                mode: currentMode
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Query execution rejected");

        document.getElementById("t-role").textContent = currentRole.toUpperCase();
        document.getElementById("t-action").textContent = data.action_type.toUpperCase();
        document.getElementById("t-src").textContent = data.classification_source.toUpperCase();
        document.getElementById("t-gen").textContent = `${data.generation_ms}ms`;
        document.getElementById("t-exec").textContent = `${data.execution_ms}ms`;
        document.getElementById("telemetry-box").classList.remove("hidden");

        document.getElementById("sql-view").textContent = data.sql;
        document.getElementById("sql-panel").classList.remove("hidden");

        if (data.action_type !== "select" && data.message) {
            successBanner.textContent = data.message;
            successBanner.classList.remove("hidden");
            fetchSchema();
        }

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
        body.innerHTML = `<tr><td colspan="${cols.length}" style="text-align:center; color:#9ca3af;">0 rows matched</td></tr>`;
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
'''

# 16. run.py
FILES["run.py"] = '''import uvicorn
import webbrowser
import threading
import time
from init_db import seed_database
from app.config import settings

def open_browser():
    time.sleep(1.5)
    url = f"http://{settings.HOST}:{settings.PORT}"
    print(f"\\n[+] Opening browser at: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    print("[*] Initializing Database...")
    seed_database()
    threading.Thread(target=open_browser, daemon=True).start()
    print(f"[*] Starting QueryMind AI Server on http://{settings.HOST}:{settings.PORT} ...")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
'''

def build():
    print("=" * 60)
    print(" ⚡ QueryMind AI: Multi-Update & Universal NLP Engine")
    print("=" * 60)

    for rel_path, content in FILES.items():
        dir_name = os.path.dirname(rel_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(rel_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"  [OK] Cleaned & Generated: {rel_path}")

    print("\n[SUCCESS] Engine successfully updated with Multi-Update Support!")
    print("=" * 60)
    print("Terminal me run karo:")
    print("   python run.py")
    print("=" * 60)

if __name__ == "__main__":
    build()