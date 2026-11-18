from typing import Any, Dict, List, Optional

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
