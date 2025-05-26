import click
import json

# from langgraph.checkpoint.memory import MemorySaver
from sql_qa.config import get_app_config, turn_logger
from shared.logger import get_main_logger, with_a_turn_logger

logger = get_main_logger(__name__, log_file="./logs/cli.log")

from sql_qa.runner import Runner

app_config = get_app_config()

logger.info(
    "--------------------------------Starting CLI--------------------------------"
)
logger.info(json.dumps(app_config.model_dump(), indent=4, ensure_ascii=False))


@click.group()
def app():
    pass


@app.command()
def cli():
    runner = Runner(app_config)
    # print(f"Hello, {name}! This is the CLI for the SQL QA app.")

    while (user_question := input("Enter a SQL question: ").lower()) not in [
        "exit",
        "quit",
        "q",
    ]:
        run_turn(runner, user_question)


@with_a_turn_logger(turn_logger)
def run_turn(runner: Runner, user_question: str):
    response = runner.run(user_question)
    if response:
        print(f"Bot: {response}")
    else:
        print("Failed to generate a response. Please try again.")


@app.command()
@click.option("--file", type=click.File("r"), help="File path to the benchmark data")
def benchmark(file):

    pass


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
