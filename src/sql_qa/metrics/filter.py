from typing import Iterator, Dict, Any, Tuple
import json
import csv
from pathlib import Path
from tqdm import tqdm
import click
from sql_qa.metrics.evaluation import read_sql_pairs_from_csv


def filter_sql_pairs(
    sql_pairs: Iterator[Dict[str, Any]],
    max_result_length: int,
    skipped_file: str = "skipped_queries.csv",
) -> Tuple[Iterator[Dict[str, Any]], int]:
    """Filter SQL pairs based on result length constraints.

    Args:
        sql_pairs: Iterator of SQL pairs from CSV
        max_result_length: Maximum allowed length for result strings
        skipped_file: Path to save details of skipped queries

    Returns:
        Tuple of (filtered SQL pairs iterator, number of skipped queries)
    """
    skipped_queries = []
    total_queries = 0

    def filter_generator():
        nonlocal total_queries
        for pair in sql_pairs:
            total_queries += 1
            ground_truth_result = pair["ground_truth_result"]
            generated_result = pair["generated_raw_result"]

            if (
                ground_truth_result
                and len(str(ground_truth_result)) > max_result_length
            ) or (generated_result and len(str(generated_result)) > max_result_length):
                skipped_queries.append(pair)
                continue

            yield pair

    # Create filtered iterator
    filtered_pairs = filter_generator()

    # Save skipped queries to CSV file
    if skipped_queries:
        with open(skipped_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=skipped_queries[0].keys())
            writer.writeheader()
            writer.writerows(skipped_queries)

    return filtered_pairs, len(skipped_queries)


def filter_csv_file(
    input_file: str, max_result_length: int, skipped_file: str = "skipped_queries.csv"
) -> Tuple[Iterator[Dict[str, Any]], int]:
    """Filter SQL pairs from a CSV file based on result length constraints.

    Args:
        input_file: Path to input CSV file
        max_result_length: Maximum allowed length for result strings
        skipped_file: Path to save details of skipped queries

    Returns:
        Tuple of (filtered SQL pairs iterator, number of skipped queries)
    """
    sql_pairs = read_sql_pairs_from_csv(input_file)
    return filter_sql_pairs(sql_pairs, max_result_length, skipped_file)


@click.group()
def cli():
    """SQL pair filtering CLI."""
    pass


@cli.command()
@click.option(
    "--input-file",
    required=True,
    help="CSV file containing SQL pairs and results",
    type=click.Path(exists=True),
)
@click.option(
    "--output-file",
    required=True,
    help="CSV file to write filtered SQL pairs",
    type=click.Path(),
)
@click.option(
    "--skipped-file",
    default="skipped_queries.csv",
    help="CSV file to write skipped queries",
    type=click.Path(),
)
@click.option(
    "--max-result-length",
    default=1000,
    help="Maximum length of result strings before skipping",
    type=int,
)
def filter_csv(
    input_file: str,
    output_file: str,
    skipped_file: str,
    max_result_length: int,
):
    """Filter SQL pairs from CSV file based on result length constraints."""
    # Filter SQL pairs
    filtered_pairs, num_skipped = filter_csv_file(
        input_file, max_result_length, skipped_file
    )

    # Write filtered pairs to output CSV
    total_processed = 0
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = None
        for pair in tqdm(filtered_pairs, desc="Writing filtered pairs"):
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=pair.keys())
                writer.writeheader()
            writer.writerow(pair)
            total_processed += 1

    click.echo(f"Total queries processed: {total_processed + num_skipped}")
    click.echo(f"Total queries filtered: {total_processed}")
    click.echo(f"Total queries skipped: {num_skipped}")
    click.echo(f"Filtered queries written to: {output_file}")
    click.echo(f"Skipped queries written to: {skipped_file}")


if __name__ == "__main__":
    cli()
