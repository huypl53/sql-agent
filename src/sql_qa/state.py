from typing import TypedDict

from sql_qa.llm.type import SqlLinkingTablesResponse


class Text2SqlResult(TypedDict):
    is_success: bool
    sql_query: str
    final_result: str
    error: str
    raw_result: str


class SqlAgentState(SqlLinkingTablesResponse):
    user_question: str
    pass
