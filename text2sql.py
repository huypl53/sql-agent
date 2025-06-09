import pathlib
from typing import Dict, List, Literal, Optional, Union
import click
import json
from langchain_mcp_adapters.client import Any
from langgraph.graph.graph import CompiledGraph
import pandas as pd
from pydantic import BaseModel
from tqdm import tqdm
import os
from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion import ChatCompletion, Choice
import asyncio

# from langgraph.checkpoint.memory import MemorySaver
from orchestrator import get_orchestrator_executor
from sql_qa.config import get_app_config, turn_logger
from shared.logger import get_main_logger, with_a_turn_logger, get_logger

from sql_qa.prompt.template import Role
from sql_qa.utils.invocation import ainvoke_agent

logger = get_main_logger(__name__, log_file="./logs/cli.log")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sql_qa.runner import Runner, RunnerResult
import uvicorn

app_config = get_app_config()

logger.info(
    "--------------------------------Starting CLI--------------------------------"
)
logger.info(json.dumps(app_config.model_dump(), indent=4, ensure_ascii=False))


runner = Runner(app_config)


class CompletionMessage(BaseModel):
    role: Literal[Role.USER, Role.ASSISTANT, Role.SYSTEM]
    content: Union[str, List[Dict[str, Any]]]


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[CompletionMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, int]] = None


@click.group()
def app():
    pass


@app.command()
def cli():
    # print(f"Hello, {name}! This is the CLI for the SQL QA app.")

    while (user_question := input("Enter a SQL question: ").lower()) not in [
        "exit",
        "quit",
        "q",
    ]:
        run_turn(user_question)


@with_a_turn_logger(turn_logger)
def run_turn(user_question: str) -> RunnerResult:
    response = runner.run(user_question)
    if response.is_success:
        print(f"Bot: {response.final_result}")
    else:
        print(
            f"Failed to generate a response. Please try again. Error: {response.error}"
        )
    return response


@app.command()
@click.option("--file", type=click.File("r", encoding="utf-8"), required=True)
def benchmark(file):
    # Read CSV file with header
    df = pd.read_csv(file, encoding="utf-8")
    total_questions = len(df)
    logger.info(f"Starting benchmark with {total_questions} questions")

    # Initialize the runner

    # Create output file with initial data
    output_file = file.name.replace(".csv", "_results.csv")
    df["generated_sql_query"] = None
    df["generated_query_result"] = None
    df["generated_sql_error"] = None
    df["generated_raw_result"] = None
    df.to_csv(output_file, index=False, encoding="utf-8")

    # Process each question and save results immediately
    pbar = tqdm(
        total=total_questions,
        position=0,
        leave=True,
        desc="Processing questions",
        unit="q",
    )

    for idx, question in enumerate(df["question"]):
        try:
            response = run_turn(question)
            # Update dataframe in memory
            df.at[idx, "generated_sql_query"] = response.sql_query
            df.at[idx, "generated_query_result"] = response.final_result
            df.at[idx, "generated_sql_error"] = response.error
            df.at[idx, "generated_raw_result"] = response.raw_result
        except Exception as e:
            logger.error(f"Error processing question {idx + 1}: {str(e)}")
            df.at[idx, "generated_sql_error"] = str(e)
        finally:
            # Save after each question
            df.to_csv(output_file, index=False, encoding="utf-8")
            pbar.update(1)
            pbar.set_description(f"Processed {pbar.n}/{total_questions} questions")

    pbar.close()
    logger.info(f"Results saved to {output_file}")


def extract_table_name_list(text):
    try:
        table_names = text.split(", ")
    except:
        # Wrong format
        return None
    # print(table_names, text)
    return table_names


agent_executor: CompiledGraph


@app.command()
def serve():
    app = FastAPI(title="SQL QA API")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    config = get_app_config()
    # Initialize logger
    logger = get_logger(
        "main",
        log_file=config.logging.log_dir,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
    )
    logger.info(f"Working directory: {os.getcwd()}")

    @app.post("/v1/chat/completions", response_model=ChatCompletion)
    async def chat_completions(request: ChatCompletionRequest):
        try:
            # Extract the last user message
            user_messages = [msg for msg in request.messages if msg.role == "user"]
            if not user_messages:
                raise HTTPException(status_code=400, detail="No user message found")

            last_message = user_messages[-1].content

            # Log user input
            logger.info(f"User: {last_message}")

            # configurable = {"configurable": {"thread_id": "1", "user_id": "1"}}
            # Process agent response
            final_response = None

            response = await ainvoke_agent(
                agent_executor,
                {"messages": request.model_dump()["messages"][-10:]},
                config={},
            )
            final_response = response["messages"][-1]
            # for step in agent_executor.stream(
            #     # {"messages": [HumanMessage(content=last_message)]},
            #     {"messages": request.model_dump()["messages"][-10:]},
            #     # config=configurable,
            #     stream_mode="values",
            # ):
            #     final_response = step["messages"][-1]
            # logger.info(f"Bot: {final_response}")

            # Log final response
            logger.info(f"Bot: {final_response}")

            # Format response in OpenAI-compatible format
            response = ChatCompletion(
                id="chatcmpl-gsv",
                created=int(pathlib.Path(__file__).stat().st_mtime),
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        message=ChatCompletionMessage(
                            role="assistant",
                            content=final_response.content if final_response else "",
                            refusal=None,
                            annotations=[],
                        ),
                        logprobs=None,
                        finish_reason="stop",
                    )
                ],
                # usage=Usage(
                #     prompt_tokens=0,
                #     completion_tokens=0,
                #     total_tokens=0,
                #     prompt_tokens_details=TokenDetails(),
                #     completion_tokens_details=CompletionTokenDetails(),
                # ),
                object="chat.completion",
                service_tier="default",
            )

            return response

        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def main() -> None:
        global agent_executor
        agent_executor = await get_orchestrator_executor()
        server_config = uvicorn.Config(
            app,
            host=config.server["host"],
            port=config.server["port"],
            log_level=config.server["log_level"],
            reload=config.server["reload"],
            workers=config.server["workers"],
        )
        server = uvicorn.Server(server_config)
        logger.info(
            f"Starting server at {config.server['host']}:{config.server['port']}"
        )
        await server.serve()

    asyncio.run(main())


@app.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "streamable-http", "sse"]),
    default="stdio",
    help="Transport type for the server",
)
@click.option(
    "--port", type=int, default=8000, help="Port number for non-stdio transports"
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host address for non-stdio transports",
)
@click.option("--mock", is_flag=True, help="Mock the server")
@click.option("--path", type=str, default="/mcp", help="Path for streamable transports")
def mcp_server(transport, port, host, path, mock):
    from fastmcp import FastMCP

    mcp = FastMCP(name="Text2SQL")
    if mock:

        def run_turn_mock(
            user_question: str = "cho tôi doanh số của từng cơ sở trong tháng 4 tính theo từng ngày",
        ):
            return (
                """
[(datetime.date(2025, 4, 1), 'Chi nhánh Hà Đông', Decimal('164000')), (datetime.date(2025, 4, 2), 'Chi nhánh Hà Đông', Decimal('307000')), (datetime.date(2025, 4, 3), 'Chi nhánh Hà Đông', Decimal('300000')), (datetime.date(2025, 4, 4), 'Chi nhánh Hà Đông', Decimal('150000')), (datetime.date(2025, 4, 5), 'Chi nhánh Hà Đông', Decimal('900000')), (datetime.date(2025, 4, 6), 'Chi nhánh Cầu Giấy', Decimal('1331000')), (datetime.date(2025, 4, 6), 'Chi nhánh Hà Đông', Decimal('0')), (datetime.date(2025, 4, 7), 'Chi nhánh Hà Đông', Decimal('1725350')), (datetime.date(2025, 4, 8), 'Chi nhánh Hà Đông', Decimal('1260000')), (datetime.date(2025, 4, 9), 'Chi nhánh Hà Đông', Decimal('131314000')), (datetime.date(2025, 4, 10), 'Chi nhánh Hà Đông', Decimal('797500')), (datetime.date(2025, 4, 12), 'Chi nhánh Hà Đông', Decimal('3000')), (datetime.date(2025, 4, 13), 'Chi nhánh Cầu Giấy', Decimal('330000')), (datetime.date(2025, 4, 14), 'Chi nhánh Hà Đông', Decimal('210000')), (datetime.date(2025, 4, 15), 'Chi nhánh Hà Đông', Decimal('662500')), (datetime.date(2025, 4, 16), 'Chi nhánh Cầu Giấy', Decimal('7000')), (datetime.date(2025, 4, 16), 'Chi nhánh Hà Đông', Decimal('787000')), (datetime.date(2025, 4, 17), 'Chi nhánh Hà Đông', Decimal('666500')), (datetime.date(2025, 4, 18), 'Chi nhánh Hà Đông', Decimal('500')), (datetime.date(2025, 4, 19), 'Chi nhánh Cầu Giấy', Decimal('676000')), (datetime.date(2025, 4, 19), 'Chi nhánh Hà Đông', Decimal('666000')), (datetime.date(2025, 4, 21), 'Chi nhánh Cầu Giấy', Decimal('1143960')), (datetime.date(2025, 4, 21), 'Chi nhánh Hà Đông', Decimal('334000')), (datetime.date(2025, 4, 22), 'Chi nhánh Cầu Giấy', Decimal('320070')), (datetime.date(2025, 4, 23), 'Chi nhánh Cầu Giấy', Decimal('715000'))]
            """,
            )

        mcp.add_tool(
            name="retrieve_data",
            description="Database query tool. Analyze the input question then generate a SQL query, execute it and return the result",
            fn=run_turn_mock,
        )
    else:
        mcp.add_tool(
            name="retrieve_data",
            description="Database query tool. Analyze the input question then generate a SQL query, execute it and return the result",
            fn=run_turn,
        )

    if transport == "stdio":
        logger.info(f"Running server on stdio")
        mcp.run()
    elif transport == "streamable-http":
        logger.info(f"Running server on streamable-http on {host}:{port}{path}")
        mcp.run(transport=transport, port=port, host=host, path=path)
    elif transport == "sse":
        logger.info(f"Running server on sse on {host}:{port}")
        mcp.run(transport=transport, port=port, host=host)


if __name__ == "__main__":
    app()
