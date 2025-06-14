import click
import json
import pandas as pd
from tqdm import tqdm

# from langgraph.checkpoint.memory import MemorySaver
from sql_qa.config import get_app_config, turn_logger
from shared.logger import get_main_logger, with_a_turn_logger

from sql_qa.state import Text2SqlResult

logger = get_main_logger(__name__, log_file="./logs/cli.log")

from sql_qa.text2sql.sql_agent import SqlAgent

app_config = get_app_config()

logger.info(
    "--------------------------------Starting CLI--------------------------------"
)
logger.info(app_config)


sql_agent = SqlAgent(app_config)


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
def run_turn(user_question: str) -> Text2SqlResult:
    response = sql_agent.run(user_question)
    if response.is_success:
        print(f"Bot: {response[ 'final_result' ]}")
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


@app.command()
def serve():
    import os

    print(os.getcwd())
    print("Serving...")


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
        mcp.tool(
            lambda user_question="cho tôi doanh số của từng cơ sở trong tháng 4 tính theo từng ngày": """
[(datetime.date(2025, 4, 1), 'Chi nhánh Hà Đông', Decimal('164000')), (datetime.date(2025, 4, 2), 'Chi nhánh Hà Đông', Decimal('307000')), (datetime.date(2025, 4, 3), 'Chi nhánh Hà Đông', Decimal('300000')), (datetime.date(2025, 4, 4), 'Chi nhánh Hà Đông', Decimal('150000')), (datetime.date(2025, 4, 5), 'Chi nhánh Hà Đông', Decimal('900000')), (datetime.date(2025, 4, 6), 'Chi nhánh Cầu Giấy', Decimal('1331000')), (datetime.date(2025, 4, 6), 'Chi nhánh Hà Đông', Decimal('0')), (datetime.date(2025, 4, 7), 'Chi nhánh Hà Đông', Decimal('1725350')), (datetime.date(2025, 4, 8), 'Chi nhánh Hà Đông', Decimal('1260000')), (datetime.date(2025, 4, 9), 'Chi nhánh Hà Đông', Decimal('131314000')), (datetime.date(2025, 4, 10), 'Chi nhánh Hà Đông', Decimal('797500')), (datetime.date(2025, 4, 12), 'Chi nhánh Hà Đông', Decimal('3000')), (datetime.date(2025, 4, 13), 'Chi nhánh Cầu Giấy', Decimal('330000')), (datetime.date(2025, 4, 14), 'Chi nhánh Hà Đông', Decimal('210000')), (datetime.date(2025, 4, 15), 'Chi nhánh Hà Đông', Decimal('662500')), (datetime.date(2025, 4, 16), 'Chi nhánh Cầu Giấy', Decimal('7000')), (datetime.date(2025, 4, 16), 'Chi nhánh Hà Đông', Decimal('787000')), (datetime.date(2025, 4, 17), 'Chi nhánh Hà Đông', Decimal('666500')), (datetime.date(2025, 4, 18), 'Chi nhánh Hà Đông', Decimal('500')), (datetime.date(2025, 4, 19), 'Chi nhánh Cầu Giấy', Decimal('676000')), (datetime.date(2025, 4, 19), 'Chi nhánh Hà Đông', Decimal('666000')), (datetime.date(2025, 4, 21), 'Chi nhánh Cầu Giấy', Decimal('1143960')), (datetime.date(2025, 4, 21), 'Chi nhánh Hà Đông', Decimal('334000')), (datetime.date(2025, 4, 22), 'Chi nhánh Cầu Giấy', Decimal('320070')), (datetime.date(2025, 4, 23), 'Chi nhánh Cầu Giấy', Decimal('715000'))]
            """,
            name="retrieve_data",
            description="Database query tool. Analyze the input question then generate a SQL query, execute it and return the result",
        )
    else:
        mcp.tool(
            run_turn,
            name="retrieve_data",
            description="Database query tool. Analyze the input question then generate a SQL query, execute it and return the result",
        )

    if transport == "stdio":
        logger.info(f"Running server on stdio")
        mcp.run(transport=transport)
    elif transport == "streamable-http":
        logger.info(f"Running server on streamable-http on {host}:{port}{path}")
        mcp.run(transport=transport, port=port, host=host, path=path)
    elif transport == "sse":
        logger.info(f"Running server on sse on {host}:{port}")
        mcp.run(transport=transport, port=port, host=host)


if __name__ == "__main__":
    app()
