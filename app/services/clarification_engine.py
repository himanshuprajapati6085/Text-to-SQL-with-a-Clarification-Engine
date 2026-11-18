import re
from typing import Dict, Any, Optional
from sqlalchemy import text
from app.schemas.request_models import ClarificationPayload, ClarificationOption
from app.services.db_manager import DBManager

class ClarificationEngine:
    @staticmethod
    def check_ambiguity(question: str, role: str, dept_id: Optional[int], student_id: Optional[int] = None) -> Optional[ClarificationPayload]:
        """
        Role-aware ambiguity detection.
        Checks for ambiguous names or missing scope within the user's authorized domain.
        """
        clean_q = question.strip()
        q_lower = clean_q.lower()

        # 1. Skip clarification for write operations (ADD, UPDATE, DELETE)
        if any(w in q_lower for w in ["add", "insert", "naya", "nayi", "jodo", "update", "badlo", "kardo", "kar do", "delete", "hatao", "set"]):
            return None

        # 2. Skip if user explicitly specified roll number or full unique identifier
        if re.search(r"\b(cse|aiml|ece)-\d{4}-\d{2}\b", q_lower) or re.search(r"\broll\s*(?:no|number)?\s*[:=]?\s*[\w-]+\b", q_lower):
            return None

        engine = DBManager.get_engine("college")
        dept_clause = f"dept_id = {dept_id}" if dept_id else "1=1"

        with engine.connect() as conn:
            # 3. Check if user typed a full specific name (e.g. 'Aarav Sharma') that matches uniquely
            all_students = conn.execute(text(f"SELECT student_id, name, roll_no FROM students WHERE {dept_clause}")).fetchall()
            for sid, sname, sroll in all_students:
                if sname.lower() in q_lower:
                    # User specified full name e.g. "Aarav Sharma", exactly 1 match! No ambiguity.
                    return None

            # 4. Check for standalone ambiguous surname or partial name (e.g. 'Sharma' or 'Verma')
            stopwords = {
                "show", "get", "fetch", "marks", "attendance", "details", "score", "record",
                "records", "student", "students", "ke", "ki", "ka", "ko", "dikhao", "batao",
                "kya", "hai", "of", "for", "in", "and", "aur", "the", "all", "what", "is"
            }
            words = [w for w in re.findall(r"[A-Za-z]+", clean_q) if len(w) >= 3 and w.lower() not in stopwords]

            for token in words:
                res = conn.execute(text(f"""
                    SELECT student_id, roll_no, name, semester, course_id
                    FROM students
                    WHERE LOWER(name) LIKE :pat AND {dept_clause}
                    ORDER BY name ASC
                """), {"pat": f"%{token.lower()}%"}).fetchall()

                if len(res) > 1:
                    options = []
                    aspect = "attendance" if "attendance" in q_lower else ("marks" if "mark" in q_lower else "academic details")
                    for row in res:
                        st_id, roll_no, st_name, sem, _ = row
                        opt_query = f"Show {aspect} of {st_name} (Roll: {roll_no})"
                        options.append(ClarificationOption(
                            label=f"{st_name} (Roll: {roll_no}, Semester {sem})",
                            query_suggestion=opt_query,
                            context={"student_id": st_id, "roll_no": roll_no, "name": st_name, "semester": sem}
                        ))

                    return ClarificationPayload(
                        needed=True,
                        message=f"Ambiguity Detected: Found {len(options)} students matching '{token}' in your department. Which student do you want to inspect?",
                        options=options
                    )

            # 5. Check for missing subject clarification on marks query
            m_single = re.search(r"(?:marks?|score)\s+(?:of|for)\s+([A-Za-z\s]+)", clean_q, re.I)
            if m_single and not any(sub in q_lower for sub in ["dbms", "database", "dsa", "structures", "network", "compiler", "cloud", "ai", "machine"]):
                cand_name = m_single.group(1).strip()
                res_st = conn.execute(
                    text(f"SELECT student_id, name FROM students WHERE LOWER(name) LIKE :name AND {dept_clause} LIMIT 1"),
                    {"name": f"%{cand_name.lower()}%"}
                ).fetchone()

                if res_st:
                    st_id, st_name = res_st
                    records = conn.execute(
                        text("SELECT subject_code, subject_name FROM academic_records WHERE student_id = :sid"),
                        {"sid": st_id}
                    ).fetchall()

                    if len(records) > 1 and "all" not in q_lower:
                        options = [
                            ClarificationOption(
                                label="All Enrolled Subjects",
                                query_suggestion=f"Show all subjects marks for {st_name}",
                                context={"subject": "ALL"}
                            )
                        ]
                        for r in records:
                            options.append(ClarificationOption(
                                label=f"{r[1]} ({r[0]})",
                                query_suggestion=f"Show marks of {st_name} in {r[1]}",
                                context={"subject_code": r[0], "subject_name": r[1]}
                            ))

                        return ClarificationPayload(
                            needed=True,
                            message=f"Please specify the subject for {st_name}'s marks:",
                            options=options
                        )

        return None
