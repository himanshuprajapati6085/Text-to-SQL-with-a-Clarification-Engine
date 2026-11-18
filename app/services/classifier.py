import re

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
