from typing import Literal, Optional, Tuple, NamedTuple, cast
from typing import List, Literal, Optional, NamedTuple, TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from shared.db import get_db
from shared.logger import logger
from sql_qa.config import turn_logger
from sql_qa.llm.strategy import StrategyFactory
from sql_qa.llm.type import (
    CandidateGenState,
    SqlLinkingTablesResponse,
    StrategyState,
)
from sql_qa.prompt.constant import CommonConstant, Text2SqlConstant
from sql_qa.prompt.template import Role
from sql_qa.llm.adapter import get_react_agent
from sql_qa.schema.store import Schema, SchemaStore
import json


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


class SqlAgent:
    def __init__(self, app_config, chat_config: dict = {}):
        self.app_config = app_config

        self.db = get_db()
        # llm = init_chat_model(app_config.llm.model, model_provider=app_config.llm.provider)
        # toolkit = SQLDatabaseToolkit(db=db, llm=llm)

        # tools = toolkit.get_tools()[:1]  # query tool only
        tools = []
        # logger.info(f"Tools: {tools}")
        self.chat_config = chat_config

        # checkpointer = MemorySaver()
        self.schema_linking_adapter = get_react_agent(
            model=self.app_config.schema_linking.model,
            tools=tools,
            prompt=Text2SqlConstant.system.format(
                dialect=self.app_config.database.dialect.upper()
            ),
            response_format=SqlLinkingTablesResponse,
            # checkpointer=checkpointer,
        )

        self.response_enhancement_adapter = get_react_agent(
            model=self.app_config.result_enhancement.model,
            tools=tools,
            prompt=Text2SqlConstant.system.format(
                dialect=self.app_config.database.dialect.upper()
            ),
            # response_format=SqlResponseEnhancementResponse,
            # checkpointer=checkpointer,
        )

        # sql_generator = LLMGeneration(chat_config)
        schema = Schema.load(self.app_config.schema_path)
        self.strategy = StrategyFactory()
        self.schema_store = SchemaStore()
        self.schema_store.add_schema(schema)

        self.graph: CompiledGraph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        graph_builder = StateGraph(SqlAgentState)
        graph_builder.add_node(SQL_AGENT_NODE.schema_linking, self.link_schema)
        graph_builder.add_node(
            SQL_AGENT_NODE.filtered_schema_tables, self.filtered_schema_tables
        )
        graph_builder.add_node(SQL_AGENT_NODE.generation, self.generation)
        # graph_builder.add_node(
        #     SQL_AGENT_NODE.response_enhancement, self.response_enhancement
        # )

        graph_builder.add_edge(START, SQL_AGENT_NODE.schema_linking)
        graph_builder.add_edge(
            SQL_AGENT_NODE.schema_linking, SQL_AGENT_NODE.filtered_schema_tables
        )
        graph_builder.add_edge(
            SQL_AGENT_NODE.filtered_schema_tables, SQL_AGENT_NODE.generation
        )
        # graph_builder.add_edge(
        #     SQL_AGENT_NODE.generation, SQL_AGENT_NODE.response_enhancement
        # )

        graph_builder.add_edge(SQL_AGENT_NODE.generation, END)
        # graph_builder.add_edge(SQL_AGENT_NODE.response_enhancement, END)

        return graph_builder.compile()

    async def link_schema(
        self, state: SqlAgentState
    ) -> Command[Literal[END, SQL_AGENT_NODE.filtered_schema_tables]]:
        user_question = state["user_question"]
        linking_response = await self.schema_linking_adapter.ainvoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": Text2SqlConstant.table_linking.format(
                            question=user_question,
                            schema=list(self.schema_store.schemas.values())[
                                0
                            ].model_dump(mode="json"),
                        ),
                    }
                ]
            },
            config=self.chat_config,
        )
        if not linking_response:
            logger.error(f"Linking response is None")
            return Command(
                goto=END,
                update=SqlAgentState(
                    is_success=False, error="Linking response is None"
                ),
            )
        linking_result = linking_response["messages"][-1]
        logger.info(f"Linking result: {linking_result.content}")
        logger.info(
            f"Linking structured result: {linking_response['structured_response']}"
        )
        structured_linking_response: SqlLinkingTablesResponse = linking_response[
            "structured_response"
        ]
        table_names = structured_linking_response["tables"]
        logger.info(f"Table names: {table_names}")
        turn_logger.log(
            "linking_structured_result",
            structured_linking_response,
        )
        if not any(structured_linking_response["tables"]):
            logger.error(f"No tables found")
            return Command(
                goto=END,
                update=SqlAgentState(is_success=False, error="No tables found"),
            )

        return Command(
            goto=SQL_AGENT_NODE.filtered_schema_tables,
            update=SqlAgentState(tables=table_names),
        )

    def filtered_schema_tables(
        self, state: SqlAgentState
    ) -> Literal[SQL_AGENT_NODE.generation]:
        table_names = state["tables"]
        filtered_schema_tables = self.schema_store.search_tables(
            table_names, mode="same", include_foreign_keys=True
        )
        logger.info(
            f"filtered_schema_tables: {[t.name for s in filtered_schema_tables.values() for t in s.tables if s]}"
        )
        turn_logger.log(
            "filtered_schema_tables",
            json.dumps(
                [
                    t.name
                    for s in filtered_schema_tables.values()
                    for t in (s.tables or [])
                    if s
                ],
                indent=4,
            ),
        )
        update: SqlAgentState = {}
        update["schema_linking"] = filtered_schema_tables
        return update

    async def generation(self, state: SqlAgentState) -> Literal[END]:
        filtered_schema_tables = state["schema_linking"]
        user_question = state["user_question"]
        strategy = self.strategy
        strategy_graph = strategy.graph
        strategy_payload: StrategyState = {}
        strategy_payload["user_question"] = user_question
        strategy_payload["schema"] = filtered_schema_tables

        strategy_results = await strategy_graph.ainvoke(strategy_payload)
        strategy_results = cast(StrategyState, strategy_results)
        turn_logger.log("strategy", strategy_results["logs"])

        strategy_logs = strategy_results["logs"]
        if not any(strategy_logs):
            logger.error(f"SQL generation failed")
            print("SQL generation failed")
            return SqlAgentState(is_success=False, error="SQL generation failed")
        best_strategy_result = strategy_logs[-1]

        final_sql = best_strategy_result["sql"]
        final_result = best_strategy_result["execution_result"]

        update: SqlAgentState = {}
        update.update(
            {
                "is_success": True,
                "error": "SQL execution failed",
                "final_sql": final_sql or "",
                "final_result": final_result or "",
            }
        )

        update.update(
            {
                "candidate_generation": strategy_logs,
            }
        )

        return update

    async def response_enhancement(self, state: SqlAgentState) -> SqlAgentState:
        user_question = state["user_question"]
        logger.info(f"User question: {user_question}")

        turn_logger.log("user_question", user_question)

        # ---

        # success, final_sql = sql_generator.invoke(user_question, filtered_schema_tables)
        if not state["candidate_generation"]:
            return SqlAgentState(is_success=False, error="Response enhancement failed!")

        for generation in state["candidate_generation"]:
            if not generation["is_correct"]:
                continue

            sql = generation["sql"]
            sql_result = generation["execution_result"]

            response_enhancement_prompt = Text2SqlConstant.response_enhancement.format(
                question=user_question,
                sql_query=sql,
                result=sql_result if sql_result else CommonConstant.empty_return_value,
            )
            turn_logger.log("response_enhancement_prompt", response_enhancement_prompt)
            response_enhancement_response = (
                await self.response_enhancement_adapter.ainvoke(
                    {
                        "messages": [
                            {
                                "role": Role.USER,
                                "content": response_enhancement_prompt,
                            }
                        ]
                    },
                    config=self.chat_config,
                )
            )
            turn_logger.log(
                f"response_enhancement_response_{generation['strategy']}",
                f" {response_enhancement_response['messages'][-1].content if response_enhancement_response else 'None'}",
            )
            # if not response_enhancement_response:
            #     logger.error(f"Response enhancement response is None")
            #     print("Response enhancement response is None")
            #     return SqlAgentState(
            #         is_success=False, error="Response enhancement response is None"
            #     )
            response_enhancement_result = response_enhancement_response["messages"][-1]
            logger.info(
                f"Response enhancement result: {response_enhancement_result.content}"
            )
            # print(f"Bot: f{response_enhancement_result.content}")
            turn_logger.log(
                f"response_enhancement_result_{generation['strategy']}",
                response_enhancement_result.content,
            )
            generation["enhanced_result"] = response_enhancement_result.content
        # return SqlAgentState(
        #     is_success=True,
        #     final_result=response_enhancement_result.content,
        #     sql_query=final_generation_result.sql,
        #     raw_result=sql_result,
        # )

    async def arun(self, user_question: str) -> SqlAgentState:
        payload: SqlAgentState = {}
        payload["user_question"] = user_question
        response = await self.graph.ainvoke(payload)
        response = cast(SqlAgentState, response)

        # logger.info(f"final_state: {response}")
        turn_logger.log("final_state", response)
        return response
