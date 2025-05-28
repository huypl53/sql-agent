import click
import json
import pandas as pd
from tqdm import tqdm

# from langgraph.checkpoint.memory import MemorySaver
from sql_qa.config import get_app_config, turn_logger
from shared.logger import get_main_logger, with_a_turn_logger

logger = get_main_logger(__name__, log_file="./logs/cli.log")

from sql_qa.runner import Runner, RunnerResult

app_config = get_app_config()

logger.info(
    "--------------------------------Starting CLI--------------------------------"
)
logger.info(json.dumps(app_config.model_dump(), indent=4, ensure_ascii=False))


runner = Runner(app_config)


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
        mcp.add_tool(
            name="text2sql_tool",
            description="Analyze the input question then generate a SQL query, execute it and return the result",
            fn=lambda input_question="Liệt kê các lịch hẹn có thời gian ước tính là 30 phút": """
            (datetime.datetime(2025, 3, 12, 6, 32, 47, 323571), datetime.datetime(2025, 3, 12, 6, 32, 47, 323571), 1, None, None, 'Vttech', None, 1, 'AP89451741761167', 'Vũ Thị Kim Huệ', 0, '0843226661', 'Admin ', '', 1, datetime.datetime(2025, 3, 12, 6, 32, 39), None, None, 30, None, None, 26, 16, 8945, 25, 1, 38, None, None), (datetime.datetime(2025, 3, 12, 13, 44, 24, 644867), datetime.datetime(2025, 4, 22, 0, 15, 27), 1, 1, None, 'Admin', 'Admin', 2, 'AP89461741787064', 'Cường nguyễn', None, '0989149111', 'Admin ', '', 1, datetime.datetime(2025, 3, 12, 13, 44, 14), None, None, 30, None, None, 26, 20, 8946, 41, 1, 46, None, None), (datetime.datetime(2025, 3, 14, 2, 46, 45, 681075), datetime.datetime(2025, 3, 14, 2, 46, 45, 681075), 1, None, None, 'Admin', None, 4, 'AP61741920405', 'Vũ Thị Thu Hà', 0, '0857892342', 'Admin ', '', 1, datetime.datetime(2025, 3, 21, 23, 0), None, None, 30, None, None, 25, 16, 6, 2, 1, 16, None, None), (datetime.datetime(2025, 3, 17, 13, 53, 15, 741183), datetime.datetime(2025, 4, 18, 12, 11, 7), 1, 1, None, 'Admin', 'Admin', 6, 'AP89581742219595', 'testphone2', None, '0379111002', 'Admin ', '', 1, datetime.datetime(2025, 3, 17, 13, 53, 13), '11', None, 30, None, None, 26, 16, 8958, 53, 2, 46, None, None), (datetime.datetime(2025, 3, 18, 2, 15, 31, 663220), datetime.datetime(2025, 3, 18, 2, 15, 31, 663220), 1, None, None, 'Admin', None, 10, 'AP11742264131', 'Anh Thư', 0, '0355293225', 'Admin ', '', 1, datetime.datetime(2025, 3, 20, 17, 0), 'Routine check-up', 'Patient unavailable', 30, None, None, 1, 1, 1, 1, 1, 1, None, None), (datetime.datetime(2025, 3, 18, 2, 16, 20, 453885), datetime.datetime(2025, 3, 18, 2, 16, 20, 453885), 1, None, None, 'Admin', None, 11, 'AP11742264180', 'Anh Thư', 0, '0355293225', 'Admin ', '', 1, datetime.datetime(2025, 3, 20, 23, 0), 'Routine check-up', 'Patient unavailable', 30, None, None, 1, 1, 1, 1, 1, 1, None, None), (datetime.datetime(2025, 3, 18, 2, 21, 49, 590649), datetime.datetime(2025, 3, 26, 6, 52, 1), 1, 1, None, 'Admin', 'Admin', 14, 'AP89581742264509', 'testphone2', None, '0379111002', 'Admin ', '', 1, datetime.datetime(2025, 3, 25, 23, 0), None, None, 30, None, None, 26, 16, 8958, 53, 1, 37, None, None), (datetime.datetime(2025, 3, 18, 15, 8, 32, 675708), datetime.datetime(2025, 3, 18, 15, 8, 32, 675708), 1, None, None, 'Admin', None, 16, 'AP89581742310512', 'testphone2', None, '0379111002', 'Admin ', '', 1, datetime.datetime(2025, 3, 18, 23, 0), 'aaa', None, 30, None, None, 26, 16, 8958, 53, 1, 46, None, None), (datetime.datetime(2025, 3, 18, 15, 40, 8, 244492), datetime.datetime(2025, 3, 18, 15, 40, 8, 244492), 1, None, None, 'Admin', None, 18, 'AP89581742312408', 'testphone2', None, '0379111002', 'Admin ', '', 1, datetime.datetime(2025, 3, 19, 0, 0), None, None, 30, None, None, 26, 16, 8958, 41, 1, 46, None, None), (datetime.datetime(2025, 3, 18, 15, 46, 52, 198898), datetime.datetime(2025, 3, 18, 15, 46, 52, 198898), 1, None, None, 'Admin', None, 19, 'AP89581742312812', 'testphone2', None, '0379111002', 'Admin ', '', 1, datetime.datetime(2025, 3, 19, 13, 0), 'p test', None, 30, None, None, 26, 16, 8958, 53, 1, 46, None, None), (datetime.datetime(2025, 3, 18, 16, 23, 13, 950939), datetime.datetime(2025, 3, 18, 16, 23, 13, 950939), 1, None, None, 'Admin', None, 20, 'AP89581742314993', 'testphone2', None, '0379111002', 'Admin ', '', 1, datetime.datetime(2025, 3, 19, 10, 0), 'eee', None, 30, None, None, 26, 16, 8958, 53, 1, 46, None, None), (datetime.datetime(2025, 3, 25, 13, 26, 26, 988270), datetime.datetime(2025, 3, 26, 1, 42, 40), 1, 1, None, 'Admin', 'Admin', 30, 'AP116301742909186', 'Hoàng Trọng Bình', None, '0985592699', 'Admin', '', 1, datetime.datetime(2025, 3, 25, 13, 26, 18), None, None, 30, None, None, 26, 16, 11630, 55, 3, 46, None, None), (datetime.datetime(2025, 3, 26, 1, 58, 34, 795471), datetime.datetime(2025, 3, 26, 7, 36, 43), 1, 1, None, 'Admin', 'Admin', 31, 'AP116301742954314', 'Hoàng Trọng Bình', None, '0985592699', 'Admin', '', 1, datetime.datetime(2025, 3, 26, 1, 58, 20), None, None, 30, None, None, 26, 249, 11630, 53, 3, 46, None, None), (datetime.datetime(2025, 3, 26, 9, 31, 11, 78968), datetime.datetime(2025, 3, 26, 9, 31, 17), 1, 1, None, 'Admin', 'Admin', 33, 'AP9191742981471', 'test', 0, '0964810858', 'Admin', '', 1, datetime.datetime(2025, 3, 26, 4, 30), None, None, 30, None, None, 25, 17, 919, 53, 1, 38, None, None), (datetime.datetime(2025, 4, 10, 2, 53, 42, 494271), datetime.datetime(2025, 4, 10, 7, 25, 51), 1, 1, None, 'Admin', 'Admin', 67, 'AP116361744253622', 'Trần Anh Phan', None, '1234567890', 'Admin', '', 1, datetime.datetime(2025, 4, 10, 2, 53, 25), None, None, 30, None, None, 26, 22, 11636, 53, 1, 38, None, 57), (datetime.datetime(2025, 4, 22, 16, 15, 33, 213839), datetime.datetime(2025, 4, 22, 16, 15, 33, 213839), 1, None, None, 'Admin', None, 97, 'AP895020250423061533536', 'cường test', None, '0980149123', 'Admin', '', 1, datetime.datetime(2025, 4, 23, 0, 0), None, None, 30, None, None, 26, 16, 8950, 8, 3, 38, None, None)
            """,
        )
    else:
        mcp.add_tool(
            name="text2sql_tool",
            description="Analyze the input question then generate a SQL query, execute it and return the result",
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
