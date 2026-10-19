from typing import Any, Dict, List, Optional
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
