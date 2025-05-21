import click
import json
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import trim_messages
from langgraph.checkpoint.memory import MemorySaver
from shared.db import get_db
from sql_qa.llm.type import (
    SQLQueryFixingResponse,
)
from sql_qa.llm.type import SQLGenerationResponse, SqlLinkingTablesResponse
from sql_qa.prompt.constant import PromptConstant
from sql_qa.prompt.template import Role
from sql_qa.llm.adapter import ApiAdapter
from sql_qa.config import get_config
from shared.logger import get_logger

from sql_qa.schema.store import Schema, SchemaStore

logger = get_logger(__name__, log_file="./logs/cli.log")

app_config = get_config()
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
        prompt=PromptConstant.system_prompt.format(
            dialect=app_config.database.dialect.upper()
        ),
        response_format=SqlLinkingTablesResponse,
        # checkpointer=checkpointer,
    )

    generation_adapter = ApiAdapter(
        model=f"{app_config.llm.provider}:{app_config.llm.model}",
        tools=tools,
        prompt=PromptConstant.system_prompt.format(
            dialect=app_config.database.dialect.upper()
        ),
        response_format=SQLGenerationResponse,
        checkpointer=checkpointer,
        # pre_model_hook=trimmer,
    )

    query_fixing_adapter = ApiAdapter(
        model=f"{app_config.llm.provider}:{app_config.llm.model}",
        tools=tools,
        prompt=PromptConstant.system_prompt.format(
            dialect=app_config.database.dialect.upper()
        ),
        response_format=SQLQueryFixingResponse,
        # checkpointer=checkpointer,
    )
    response_enhancement_adapter = ApiAdapter(
        model=f"{app_config.llm.provider}:{app_config.llm.model}",
        tools=tools,
        prompt=PromptConstant.system_prompt.format(
            dialect=app_config.database.dialect.upper()
        ),
        # checkpointer=checkpointer,
    )
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
                        "content": PromptConstant.table_linking_prompt.format(
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

        filtered_schema_tables = schema_store.search_tables(
            table_names, mode="connected"
        )
        logger.info(
            f"filtered_schema_tables: {[t.name for s in filtered_schema_tables.values() for t in s.tables if s]}"
        )

        run_iter = 0
        response_is_correct = False
        generation_evidence = ""
        final_sql = ""
        while run_iter < 2 and not response_is_correct:
            logger.info(
                f"Run iteration: {run_iter}; Evidence: {generation_evidence}; Response is correct: {response_is_correct}"
            )
            run_iter += 1
            generation_response = generation_adapter.invoke(
                {
                    "messages": [
                        {
                            "role": Role.ASSISTANT,
                            "content": PromptConstant.direct_generation_prompt.format(
                                question=user_question,
                                evidence=generation_evidence,
                                schema=filtered_schema_tables,
                            ),
                        }
                    ]
                },
                config=chat_config,
            )
            if not generation_response:
                logger.error(f"Generation response is None")
                continue
            generation_result = generation_response["messages"][-1]
            logger.info(f"SQL Generation result: {generation_result.content}")
            logger.info(
                f"SQL Generation structured result: {generation_response['structured_response']}"
            )
            structured_generation_response: SQLGenerationResponse = generation_response[
                "structured_response"
            ]
            sql = structured_generation_response.sql
            final_sql = sql
            logger.info(f"SQL: {sql}")
            logger.info(f"Explanation: {structured_generation_response.explanation}")

            # response_is_correct = True
            # break
            query_fixing_response = query_fixing_adapter.invoke(
                {
                    "messages": [
                        {
                            "role": Role.ASSISTANT,
                            "content": PromptConstant.query_fixing_prompt.format(
                                question=user_question,
                                query=sql,
                                dialect=app_config.database.dialect.upper(),
                            ),
                        }
                    ]
                },
                config=chat_config,
            )
            if not query_fixing_response:
                logger.error(f"Query fixing response is None")
                continue
            query_fixing_result = query_fixing_response["messages"][-1]
            logger.info(f"Query fixing result: {query_fixing_result.content}")
            structured_query_fixing_response: SQLQueryFixingResponse = (
                query_fixing_response["structured_response"]
            )
            logger.info(
                f"Query fixing structured result: {structured_query_fixing_response}"
            )
            if structured_query_fixing_response.is_correct:
                logger.info(f"Query is correct")
                response_is_correct = True
            else:
                logger.info(f"Query is incorrect")
                logger.info(
                    f"Explanation: {structured_query_fixing_response.explanation}"
                )
                generation_evidence = structured_query_fixing_response.explanation
                response_is_correct = False

        logger.info(f"Final SQL: {final_sql}")
        if not response_is_correct:
            logger.info(
                f"Final resposne is correct: {response_is_correct}; Final explanation: {generation_evidence}"
            )
            print("Query is incorrect, please try again.")
            continue

        logger.info(
            f"Final resposne is correct: {response_is_correct}; Final explanation: {generation_evidence}"
        )
        response_enhancement_response = response_enhancement_adapter.invoke(
            {
                "messages": [
                    {
                        "role": Role.ASSISTANT,
                        "content": PromptConstant.response_enhancement_prompt.format(
                            question=user_question,
                            result=final_sql,
                        ),
                    }
                ]
            },
            config=chat_config,
        )
        if not response_enhancement_response:
            logger.error(f"Response enhancement response is None")
            continue
        response_enhancement_result = response_enhancement_response["messages"][-1]
        logger.info(
            f"Response enhancement result: {response_enhancement_result.content}"
        )
        print(response_enhancement_result.content)


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
