import time

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
