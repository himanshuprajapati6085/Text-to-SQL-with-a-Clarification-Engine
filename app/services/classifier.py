from typing import Optional
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
