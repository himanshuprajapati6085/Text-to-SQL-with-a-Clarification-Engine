import datetime
from typing import List, Optional
from sqlalchemy import text
from app.schemas.request_models import AuditLogEntry
from app.services.db_manager import DBManager

class AuditService:
    @staticmethod
    def log(
        user_id: Optional[int],
        user_name: Optional[str],
        role: Optional[str],
        dept_id: Optional[int],
        action_type: str,
        status: str,
        original_prompt: str,
        executed_sql: Optional[str] = None,
        guardrail_applied: Optional[str] = None,
        reason: Optional[str] = None
    ):
        try:
            engine = DBManager.get_engine("college")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sql_clean = (executed_sql or "").replace("'", "''")
            prompt_clean = (original_prompt or "").replace("'", "''")
            guardrail_clean = (guardrail_applied or "").replace("'", "''")
            reason_clean = (reason or "").replace("'", "''")
            name_clean = (user_name or "Anonymous").replace("'", "''")
            role_clean = (role or "STUDENT").upper()

            with engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO audit_logs (
                        timestamp, user_id, user_name, role, dept_id,
                        action_type, status, original_prompt, executed_sql,
                        guardrail_applied, reason
                    ) VALUES (
                        '{now}', {user_id or 'NULL'}, '{name_clean}', '{role_clean}',
                        {dept_id or 'NULL'}, '{action_type}', '{status}',
                        '{prompt_clean}', '{sql_clean}', '{guardrail_clean}', '{reason_clean}'
                    );
                """))
        except Exception as e:
            print(f"[WARN] Failed to write audit log: {e}")

    @staticmethod
    def get_recent_logs(limit: int = 50) -> List[AuditLogEntry]:
        try:
            engine = DBManager.get_engine("college")
            with engine.connect() as conn:
                res = conn.execute(text(f"""
                    SELECT log_id, timestamp, user_id, user_name, role, dept_id,
                           action_type, status, original_prompt, executed_sql,
                           guardrail_applied, reason
                    FROM audit_logs
                    ORDER BY log_id DESC
                    LIMIT {limit}
                """))
                logs = []
                for row in res.fetchall():
                    logs.append(AuditLogEntry(
                        log_id=row[0],
                        timestamp=row[1],
                        user_id=row[2],
                        user_name=row[3],
                        role=row[4],
                        dept_id=row[5],
                        action_type=row[6],
                        status=row[7],
                        original_prompt=row[8],
                        executed_sql=row[9],
                        guardrail_applied=row[10],
                        reason=row[11]
                    ))
                return logs
        except Exception as e:
            print(f"[ERROR] Failed to fetch audit logs: {e}")
            return []
