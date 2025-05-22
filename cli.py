import click
import json
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import trim_messages
from langgraph.checkpoint.memory import MemorySaver
from shared.logger import get_main_logger

from shared.db import get_db
from sql_qa.llm.generation import LLMGeneration
from sql_qa.llm.strategy import StategyFactory
from sql_qa.llm.type import SqlLinkingTablesResponse, SqlResponseEnhancementResponse
from sql_qa.prompt.constant import PromptConstant
from sql_qa.prompt.template import Role
from sql_qa.llm.adapter import ApiAdapter
from sql_qa.config import get_app_config

from sql_qa.schema.store import Schema, SchemaStore

logger = get_main_logger(__name__, log_file="./logs/cli.log")

app_config = get_app_config()
logger.info(json.dumps(app_config.model_dump(), indent=4, ensure_ascii=False))


@click.group()
def app():
    pass


@app.command()
# @click.option("--name", prompt="Your name", help="The name to greet")
def cli():
    # print(f"Hello, {name}! This is the CLI for the SQL QA app.")

    db = get_db()
    # llm = init_chat_model(app_config.llm.model, model_provider=app_config.llm.provider)
    # toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # tools = toolkit.get_tools()[:1]  # query tool only
    tools = []
    # logger.info(f"Tools: {tools}")
    chat_config = {"configurable": {"thread_id": "1", "user_id": "1"}}

    checkpointer = MemorySaver()
    schema_linking_adapter = ApiAdapter(
        model=f"{app_config.llm.provider}:{app_config.llm.model}",
        tools=tools,
        prompt=PromptConstant.system.format(
            dialect=app_config.database.dialect.upper()
        ),
        response_format=SqlLinkingTablesResponse,
        # checkpointer=checkpointer,
    )

    response_enhancement_adapter = ApiAdapter(
        model=f"{app_config.llm.provider}:{app_config.llm.model}",
        tools=tools,
        prompt=PromptConstant.system.format(
            dialect=app_config.database.dialect.upper()
        ),
        response_format=SqlResponseEnhancementResponse,
        # checkpointer=checkpointer,
    )

    # sql_generator = LLMGeneration(chat_config)
    schema = Schema.load(app_config.schema_path)
    schema_store = SchemaStore()
    schema_store.add_schema(schema)

    while (user_question := input("Enter a SQL question: ").lower()) not in [
        "exit",
        "quit",
        "q",
    ]:
        logger.info(f"User question: {user_question}")
        linking_response = schema_linking_adapter.invoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": PromptConstant.table_linking.format(
                            question=user_question,
                            schema=list(schema_store.schemas.values())[0].model_dump(
                                mode="json"
                            ),
                        ),
                    }
                ]
            },
            config=chat_config,
        )
        if not linking_response:
            logger.error(f"Linking response is None")
            continue
        linking_result = linking_response["messages"][-1]
        logger.info(f"Linking result: {linking_result.content}")
        logger.info(
            f"Linking structured result: {linking_response['structured_response']}"
        )
        structured_linking_response: SqlLinkingTablesResponse = linking_response[
            "structured_response"
        ]
        table_names = structured_linking_response.tables
        logger.info(f"Table names: {table_names}")

        filtered_schema_tables = schema_store.search_tables(table_names, mode="same")
        logger.info(
            f"filtered_schema_tables: {[t.name for s in filtered_schema_tables.values() for t in s.tables if s]}"
        )

        # success, final_sql = sql_generator.invoke(user_question, filtered_schema_tables)
        strategy = StategyFactory(return_all=False)
        strategy_results = strategy.generate(user_question, filtered_schema_tables)

        if not any(strategy_results):
            logger.error(f"SQL generation failed")
            print("SQL generation failed")
            continue
        success, final_sql = strategy_results[0]

        if not success:
            logger.error(f"SQL generation failed")
            print("SQL generation failed")
            continue

        try:
            sql_result = db.run(final_sql)
            logger.info(f"SQL result: {sql_result}")
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            print("SQL execution failed")
            continue

        response_enhancement_response = response_enhancement_adapter.invoke(
            {
                "messages": [
                    {
                        "role": Role.ASSISTANT,
                        "content": PromptConstant.response_enhancement.format(
                            question=user_question,
                            sql_query=final_sql,
                            result=sql_result,
                        ),
                    }
                ]
            },
            config=chat_config,
        )
        if not response_enhancement_response:
            logger.error(f"Response enhancement response is None")
            print("Response enhancement response is None")
            continue
        response_enhancement_result = response_enhancement_response["messages"][-1]
        logger.info(
            f"Response enhancement result: {response_enhancement_result.content}"
        )
        print(f"Bot: f{response_enhancement_result.content}")


def extract_table_name_list(text):
    try:
        table_names = text.split(", ")
    except:
        # Wrong format
        return None
    # print(table_names, text)
    return table_names


@app.command()
def serve():
    import os

    print(os.getcwd())
    print("Serving...")


if __name__ == "__main__":
    app()
