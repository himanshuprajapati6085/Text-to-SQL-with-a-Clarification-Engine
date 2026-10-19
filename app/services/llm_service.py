import json
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
                rem_clean = rem.strip(" .,;:'\"")
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
                    return ";\n".join(sql_statements)
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
            sql = "\n".join([line for line in sql.split("\n") if not line.startswith("```")]).strip()
        return sql
