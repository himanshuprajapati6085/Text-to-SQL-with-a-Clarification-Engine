import re

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
