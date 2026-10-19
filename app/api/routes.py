import time
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
