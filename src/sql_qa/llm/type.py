from enum import Enum
from typing import List, Literal, Optional, TypedDict, Any, NamedTuple, Annotated
import operator


# GRAPH_NODE = _GraphNode()


class LlmResponse(TypedDict, total=False):
    pass


class SqlLinkingResponse(LlmResponse):
    schema_linking: Any


class SqlLinkingTablesResponse(SqlLinkingResponse):
    tables: List[str]


class SQLGenerationResponse(LlmResponse):
    sql: str
    explaination: Optional[str]


class SQLQueryValidationResponse(LlmResponse):
    is_sql_correct: bool
    explaination: Optional[str]


class SQLQueryFixerResponse(LlmResponse):
    sql: str
    explaination: Optional[str]


class SqlResponseEnhancementResponse(LlmResponse):
    enhanced_result: str


# --- Candidate Generateion
_GEN_GRAPH_NODE = Literal[
    "candidate", "validate", "fix", "enhance", "merge", "should_fix"
]


class GEN_GRAPH_NODE(NamedTuple):
    init = "init"
    candidate = "candidate"
    validate = "validate"
    fix = "fix"
    enhance = "enhance"
    merge = "merge"
    route = "route"
    should_fix = "should_fix"


class LogStep(TypedDict):
    name: _GEN_GRAPH_NODE | str
    value: Any


class CandidateGenState(
    SQLGenerationResponse, SQLQueryValidationResponse, SQLQueryFixerResponse
):
    user_question: str
    execution_result: Optional[Any]
    is_execution_correct: bool
    strategy: Optional[str]
    enhanced_result: Optional[str]
    schema: Any
    logs: Annotated[List[LogStep], operator.add]
    run_iter: int
    error: Optional[str]
    correct_thoughts: Annotated[List[LogStep], operator.add]
    evidence: Optional[str]
    # explaination: Optional[str]
    # is_correct: bool


# --- strategy
class STRAT_GRAPH_NODE(NamedTuple):
    merge = "merge"
    strategy_gen = "strategy_gen"
    route = "route"


class StrategyCandidate(TypedDict):
    strategy: str
    thoughts: List[LogStep]
    sql: Optional[str]
    execution_result: Optional[str]
    is_success: Optional[bool]


class StrategyState(TypedDict):
    schema: Any
    user_question: str
    strategy: str
    logs: Annotated[List[StrategyCandidate], operator.add]
