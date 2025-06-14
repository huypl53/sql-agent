from typing import Optional, Tuple, NamedTuple
from shared.db import get_db
from shared.logger import get_main_logger, with_a_turn_logger
from sql_qa.llm.strategy import StategyFactory
from sql_qa.llm.type import SqlLinkingTablesResponse, SqlResponseEnhancementResponse
from sql_qa.prompt.constant import CommonConstant, Text2SqlConstant
from sql_qa.prompt.template import Role
from sql_qa.llm.adapter import ApiAdapter, get_react_agent
from sql_qa.schema.store import Schema, SchemaStore
from sql_qa.config import get_app_config, turn_logger
import json

from sql_qa.state import Text2SqlResult
from sql_qa.state import SqlAgentState

logger = get_main_logger(__name__)


class _Tool(NamedTuple):
    schema_linking
    response_enhancement


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
        self.schema_store = SchemaStore()
        self.schema_store.add_schema(schema)

    async def link_schema_tool(self, state: SqlAgentState):

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
            return Text2SqlResult(is_success=False, error="Linking response is None")
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
            structured_linking_response.model_dump_json(indent=4),
        )
        if not any(structured_linking_response["tables"]):
            logger.error(f"No tables found")
            return Text2SqlResult(is_success=False, error="No tables found")

    def run(self, user_question: str) -> Text2SqlResult:
        logger.info(f"User question: {user_question}")

        turn_logger.log("user_question", user_question)

        # ---
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
                    for t in s.tables
                    if s
                ],
                indent=4,
            ),
        )

        # success, final_sql = sql_generator.invoke(user_question, filtered_schema_tables)
        strategy = StategyFactory(return_all=False)
        strategy_results = strategy.generate(user_question, filtered_schema_tables)

        if not any(strategy_results):
            logger.error(f"SQL generation failed")
            print("SQL generation failed")
            return Text2SqlResult(is_success=False, error="SQL generation failed")
        final_generation_result = strategy_results[0]

        if not final_generation_result.is_correct:
            logger.error(f"SQL generation failed")
            print("SQL generation failed")
            return Text2SqlResult(is_success=False, error="SQL generation failed")

        try:
            sql_result = self.db.run(final_generation_result.sql)
            logger.info(f"SQL result: {sql_result}")
            turn_logger.log("sql_result", sql_result)
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            turn_logger.log("error", f"SQL execution failed: {e}")
            # print("SQL execution failed")
            return Text2SqlResult(is_success=False, error="SQL execution failed")

        response_enhancement_prompt = Text2SqlConstant.response_enhancement.format(
            question=user_question,
            sql_query=final_generation_result.sql,
            result=sql_result if sql_result else CommonConstant.empty_return_value,
        )
        turn_logger.log("response_enhancement_prompt", response_enhancement_prompt)
        response_enhancement_response = self.response_enhancement_adapter.invoke(
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
        turn_logger.log(
            "response_enhancement_response",
            f" {response_enhancement_response['messages'][-1].content if response_enhancement_response else 'None'}",
        )
        if not response_enhancement_response:
            logger.error(f"Response enhancement response is None")
            print("Response enhancement response is None")
            return Text2SqlResult(
                is_success=False, error="Response enhancement response is None"
            )
        response_enhancement_result = response_enhancement_response["messages"][-1]
        logger.info(
            f"Response enhancement result: {response_enhancement_result.content}"
        )
        print(f"Bot: f{response_enhancement_result.content}")
        turn_logger.log(
            "response_enhancement_result", response_enhancement_result.content
        )
        return Text2SqlResult(
            is_success=True,
            final_result=response_enhancement_result.content,
            sql_query=final_generation_result.sql,
            raw_result=sql_result,
        )
