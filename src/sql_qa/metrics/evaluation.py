from typing import List, Tuple, Optional, Set, Iterator, Dict, Any
from dataclasses import dataclass, asdict
import re
from shared.db import get_db
import click
from enum import Enum, auto
import json
import csv
from pathlib import Path
from tqdm import tqdm
import sqlglot
from sql_qa.config import get_app_config


class MetricType(Enum):
    EXACT_MATCH = auto()
    EXECUTION_MATCH = auto()


app_config = get_app_config()


@dataclass
class EvaluationResult:
    metrics: dict  # Dictionary of metric name to score
    total_queries: int
    detailed_results: List[
        Tuple[str, str, dict]
    ]  # (predicted, ground_truth, {metric_name: is_match})

    def to_dict(self):
        """Convert the evaluation result to a dictionary for JSON serialization."""
        return {
            "summary": {"total_queries": self.total_queries, "metrics": self.metrics},
            "detailed_results": [
                {"predicted": pred, "ground_truth": truth, "metrics": metrics}
                for pred, truth, metrics in self.detailed_results
            ],
        }


class SQLMetrics:
    def __init__(self, metrics: Set[MetricType] = None):
        """Initialize the metrics evaluator.

        Args:
            metrics: Set of metrics to evaluate. If None, evaluates all metrics.
        """
        self.db = get_db()
        self.metrics = metrics or set(MetricType)

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL query for comparison by:
        1. Converting to lowercase
        2. Removing extra whitespace
        3. Standardizing quotes
        4. Removing semicolons

        Args:
            sql: SQL query string

        Returns:
            Normalized SQL query string
        """
        try:
            return sqlglot.transpile(
                sql, write=app_config.database.dialect.lower(), pretty=True
            )[0]
        except Exception:
            return ""

    def _execute_query(self, sql: str) -> Optional[List[Tuple]]:
        """Execute a SQL query and return the results.

        Args:
            sql: SQL query string

        Returns:
            Query results as a list of tuples, or None if execution fails
        """
        try:
            return self.db.run(sql)
        except Exception as e:
            print(f"Error executing query: {e}")
            return None

    def evaluate_queries(
        self, predicted_queries: List[str], ground_truth_queries: List[str]
    ) -> EvaluationResult:
        """Evaluate a list of predicted queries against ground truth queries.

        Args:
            predicted_queries: List of predicted SQL queries
            ground_truth_queries: List of ground truth SQL queries

        Returns:
            EvaluationResult containing requested metrics
        """
        # if len(predicted_queries) != len(ground_truth_queries):
        #     raise ValueError(
        #         "Number of predicted queries must match number of ground truth queries"
        #     )

        detailed_results = []
        metric_scores = {metric: 0 for metric in self.metrics}
        # total_queries = len(predicted_queries)
        total_queries = 0

        for pred, truth in zip(predicted_queries, ground_truth_queries):
            total_queries += 1
            query_results = {}

            # Evaluate exact match if requested
            if MetricType.EXACT_MATCH in self.metrics:
                norm_pred = self._normalize_sql(pred)
                norm_truth = self._normalize_sql(truth)
                is_exact_match = norm_pred == norm_truth
                query_results["exact_match"] = is_exact_match
                if is_exact_match:
                    metric_scores[MetricType.EXACT_MATCH] += 1

            # Evaluate execution match if requested
            if MetricType.EXECUTION_MATCH in self.metrics:
                pred_results = self._execute_query(pred)
                truth_results = self._execute_query(truth)
                is_execution_match = (
                    pred_results is not None
                    and truth_results is not None
                    and pred_results == truth_results
                )
                query_results["execution_match"] = is_execution_match
                if is_execution_match:
                    metric_scores[MetricType.EXECUTION_MATCH] += 1

            detailed_results.append((pred, truth, query_results))

        # Calculate final scores
        final_scores = {
            metric.name.lower(): score / total_queries if total_queries > 0 else 0
            for metric, score in metric_scores.items()
        }

        return EvaluationResult(
            metrics=final_scores,
            total_queries=total_queries,
            detailed_results=detailed_results,
        )


def read_sql_pairs_from_csv(csv_file: str) -> Iterator[Dict[str, Any]]:
    """Read SQL pairs from CSV file row by row.

    Expected CSV columns:
    - question: The natural language question
    - generated_sql_query: The predicted SQL query
    - ground_truth_sql: The ground truth SQL query
    - generated_query_result: The execution result of predicted query
    - ground_truth_result: The execution result of ground truth query

    Args:
        csv_file: Path to the CSV file

    Yields:
        Dictionary containing the SQL pairs and their execution results
    """
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                "question": row["question"],
                "predicted_sql": row["generated_sql_query"],
                "ground_truth_sql": row["ground_truth_sql"],
                "predicted_result": row["generated_query_result"],
                "ground_truth_result": row["ground_truth_result"],
            }


@click.group()
def cli():
    """SQL evaluation metrics CLI."""
    pass


@cli.command()
@click.option(
    "--predicted-file", required=True, help="File containing predicted SQL queries"
)
@click.option(
    "--ground-truth-file",
    required=True,
    help="File containing ground truth SQL queries",
)
@click.option(
    "--metrics",
    multiple=True,
    type=click.Choice(["exact_match", "execution_match"]),
    default=["exact_match", "execution_match"],
    help="Metrics to evaluate",
)
@click.option(
    "--output-file",
    required=True,
    help="File to write evaluation results (JSON format)",
)
def evaluate_files(
    predicted_file: str, ground_truth_file: str, metrics: List[str], output_file: str
):
    """Evaluate SQL queries from separate files using specified metrics and write results to JSON file."""
    # Convert metric names to MetricType enum
    metric_types = {MetricType[m.upper()] for m in metrics}

    # Initialize evaluator
    evaluator = SQLMetrics(metric_types)

    # Read queries from files
    with open(predicted_file, "r", encoding="utf-8") as f:
        predicted_queries = [line.strip() for line in f if line.strip()]

    with open(ground_truth_file, "r", encoding="utf-8") as f:
        ground_truth_queries = [line.strip() for line in f if line.strip()]

    # Evaluate queries with progress bar
    detailed_results = []
    metric_scores = {metric: 0 for metric in metric_types}

    for pred, truth in tqdm(
        zip(predicted_queries, ground_truth_queries),
        desc="Evaluating queries",
        unit="query",
    ):
        query_results = {}

        # Evaluate exact match if requested
        if MetricType.EXACT_MATCH in metric_types:
            norm_pred = evaluator._normalize_sql(pred)
            norm_truth = evaluator._normalize_sql(truth)
            is_exact_match = norm_pred == norm_truth
            query_results["exact_match"] = is_exact_match
            if is_exact_match:
                metric_scores[MetricType.EXACT_MATCH] += 1

        # Evaluate execution match if requested
        if MetricType.EXECUTION_MATCH in metric_types:
            pred_results = evaluator._execute_query(pred)
            truth_results = evaluator._execute_query(truth)
            is_execution_match = (
                pred_results is not None
                and truth_results is not None
                and pred_results == truth_results
            )
            query_results["execution_match"] = is_execution_match
            if is_execution_match:
                metric_scores[MetricType.EXECUTION_MATCH] += 1

        detailed_results.append((pred, truth, query_results))

    # Calculate final scores
    total_queries = len(predicted_queries)
    final_scores = {
        metric.name.lower(): score / total_queries if total_queries > 0 else 0
        for metric, score in metric_scores.items()
    }

    # Create result object
    result = EvaluationResult(
        metrics=final_scores,
        total_queries=total_queries,
        detailed_results=detailed_results,
    )

    # Write results to JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    click.echo(f"Evaluation results written to {output_file}")


@cli.command()
@click.option(
    "--input-file", required=True, help="CSV file containing SQL pairs and results"
)
@click.option(
    "--metrics",
    multiple=True,
    type=click.Choice(["exact_match", "execution_match"]),
    default=["exact_match", "execution_match"],
    help="Metrics to evaluate",
)
@click.option(
    "--output-file",
    required=True,
    help="File to write evaluation results (JSON format)",
)
def evaluate_csv(input_file: str, metrics: List[str], output_file: str):
    """Evaluate SQL queries from CSV file using specified metrics and write results to JSON file."""
    # Convert metric names to MetricType enum
    metric_types = {MetricType[m.upper()] for m in metrics}

    # Initialize evaluator
    evaluator = SQLMetrics(metric_types)

    # Read and evaluate queries using generator
    detailed_results = []
    metric_scores = {metric: 0 for metric in metric_types}
    total_queries = 0

    for pair in tqdm(
        read_sql_pairs_from_csv(input_file), desc="Evaluating queries", unit="query"
    ):
        total_queries += 1
        query_results = {}

        # Evaluate exact match if requested
        if MetricType.EXACT_MATCH in metric_types:
            norm_pred = evaluator._normalize_sql(pair["predicted_sql"])
            norm_truth = evaluator._normalize_sql(pair["ground_truth_sql"])
            is_exact_match = norm_pred == norm_truth
            query_results["exact_match"] = is_exact_match
            if is_exact_match:
                metric_scores[MetricType.EXACT_MATCH] += 1

        # Evaluate execution match if requested
        if MetricType.EXECUTION_MATCH in metric_types:
            is_execution_match = (
                pair["predicted_result"] is not None
                and pair["ground_truth_result"] is not None
                and pair["predicted_result"] == pair["ground_truth_result"]
            )
            query_results["execution_match"] = is_execution_match
            if is_execution_match:
                metric_scores[MetricType.EXECUTION_MATCH] += 1

        detailed_results.append(
            {
                "question": pair["question"],
                "predicted": pair["predicted_sql"],
                "ground_truth": pair["ground_truth_sql"],
                "metrics": query_results,
            }
        )

    # Calculate final scores
    final_scores = {
        metric.name.lower(): score / total_queries if total_queries > 0 else 0
        for metric, score in metric_scores.items()
    }

    # Create result object
    result = EvaluationResult(
        metrics=final_scores,
        total_queries=total_queries,
        detailed_results=detailed_results,
    )

    # Write results to JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    click.echo(f"Evaluation results written to {output_file}")


if __name__ == "__main__":
    cli()
