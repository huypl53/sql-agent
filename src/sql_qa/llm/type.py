from typing import List, Optional
from pydantic import BaseModel


class LlmResponse(BaseModel):
    pass


class GenerationResult(BaseModel):
    sql: Optional[str]
    execution_result: Optional[str]
    is_correct: bool


class SqlLinkingResponse(LlmResponse):
    result: str


class SqlLinkingTablesResponse(LlmResponse):
    tables: List[str]


class SQLGenerationResponse(LlmResponse):
    sql: str
    explanation: Optional[str]


class SQLQueryValidationResponse(LlmResponse):
    is_correct: bool
    explanation: Optional[str]


class SQLQueryFixerResponse(LlmResponse):
    sql: str
    explanation: Optional[str]


class SqlResponseEnhancementResponse(LlmResponse):
    enhanced_result: str
