from typing import List, Optional
from pydantic import BaseModel


class LlmResponse(BaseModel):
    pass


class SqlLinkingResponse(LlmResponse):
    result: str


class SqlLinkingTablesResponse(LlmResponse):
    tables: List[str]


class SQLGenerationResponse(LlmResponse):
    sql: str
    explanation: Optional[str]


class SQLQueryFixingResponse(LlmResponse):
    is_correct: bool
    explanation: Optional[str]
