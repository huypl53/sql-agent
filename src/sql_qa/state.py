from typing import List, Optional, NamedTuple

from sql_qa.llm.type import (
    SqlLinkingTablesResponse,
    SQLGenerationResponse,
    CandidateGenState,
)


class SQL_AGENT_NODE(NamedTuple):
    schema_linking = "schema_linking_node"
    filtered_schema_tables = "filtered_schema_tables_node"
    generation = "generation_node"
    response_enhancement = "response_enhancement_node"


class SqlAgentState(SqlLinkingTablesResponse, SQLGenerationResponse):
    user_question: str
    is_success: bool
    final_sql: str
    final_result: str
    error: str
    raw_result: str
    candidate_generation: Optional[List[CandidateGenState]]
    # schema_linking: List[Any]
