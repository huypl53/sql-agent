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
def run_turn(runner: Runner, user_question: str) -> RunnerResult:
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
    runner = Runner(app_config)

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
            response = run_turn(runner, question)
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


if __name__ == "__main__":
    app()
