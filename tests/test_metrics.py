import unittest
from src.sql_qa.metrics.evaluation import SQLMetrics, MetricType, EvaluationResult
from shared.db import get_db


class TestSQLMetrics(unittest.TestCase):
    def setUp(self):
        # Initialize database with test data
        self.db = get_db()
        self.db.run(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                age INTEGER,
                city TEXT
            )
        """
        )

        # Clear existing data
        self.db.run("DELETE FROM users")

        # Insert test data
        self.db.run(
            """
            INSERT INTO users (name, age, city) VALUES
            ('John', 25, 'New York'),
            ('Alice', 30, 'London'),
            ('Bob', 35, 'Paris'),
            ('Carol', 28, 'Tokyo')
        """
        )

        # Initialize metrics evaluator with all metrics
        self.metrics = SQLMetrics()

    def test_exact_match(self):
        # Test cases for exact match
        predicted_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users WHERE city = 'London'",
            "SELECT COUNT(*) FROM users",  # Different but equivalent query
        ]

        ground_truth_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users WHERE city = 'London'",
            "SELECT COUNT(id) FROM users",  # Different but equivalent query
        ]

        result = self.metrics.evaluate_queries(predicted_queries, ground_truth_queries)

        # Check exact match scores
        self.assertIn("exact_match", result.metrics)
        self.assertAlmostEqual(result.metrics["exact_match"], 2 / 3)

        # Check detailed results
        self.assertEqual(len(result.detailed_results), 3)
        self.assertTrue(result.detailed_results[0][2]["exact_match"])
        self.assertTrue(result.detailed_results[1][2]["exact_match"])
        self.assertFalse(result.detailed_results[2][2]["exact_match"])

    def test_execution_match(self):
        # Test cases for execution match
        predicted_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users WHERE city = 'London'",
            "SELECT COUNT(*) FROM users",  # Different but equivalent query
            "SELECT name FROM users WHERE age > 30",  # Different results
        ]

        ground_truth_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users WHERE city = 'London'",
            "SELECT COUNT(id) FROM users",  # Different but equivalent query
            "SELECT name FROM users WHERE age > 35",  # Different results
        ]

        result = self.metrics.evaluate_queries(predicted_queries, ground_truth_queries)

        # Check execution match scores
        self.assertIn("execution_match", result.metrics)
        self.assertAlmostEqual(result.metrics["execution_match"], 3 / 4)

        # Check detailed results
        self.assertEqual(len(result.detailed_results), 4)
        self.assertTrue(result.detailed_results[0][2]["execution_match"])
        self.assertTrue(result.detailed_results[1][2]["execution_match"])
        self.assertTrue(result.detailed_results[2][2]["execution_match"])
        self.assertFalse(result.detailed_results[3][2]["execution_match"])

    def test_invalid_queries(self):
        # Test handling of invalid queries
        predicted_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM nonexistent_table",  # Invalid table
            "SELECT name FROM users WHERE invalid_column = 1",  # Invalid column
        ]

        ground_truth_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users",
            "SELECT name FROM users",
        ]

        result = self.metrics.evaluate_queries(predicted_queries, ground_truth_queries)

        # Check execution match scores
        self.assertIn("execution_match", result.metrics)
        self.assertAlmostEqual(result.metrics["execution_match"], 1 / 3)

        # Check detailed results
        self.assertEqual(len(result.detailed_results), 3)
        self.assertTrue(result.detailed_results[0][2]["execution_match"])
        self.assertFalse(result.detailed_results[1][2]["execution_match"])
        self.assertFalse(result.detailed_results[2][2]["execution_match"])

    def test_metric_selection(self):
        # Test evaluating only specific metrics
        metrics = SQLMetrics(metrics={MetricType.EXACT_MATCH})

        predicted_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users WHERE city = 'London'",
        ]

        ground_truth_queries = [
            "SELECT name FROM users WHERE age > 25",
            "SELECT * FROM users WHERE city = 'London'",
        ]

        result = metrics.evaluate_queries(predicted_queries, ground_truth_queries)

        # Should only have exact match metric
        self.assertIn("exact_match", result.metrics)
        self.assertNotIn("execution_match", result.metrics)

        # Check detailed results
        self.assertEqual(len(result.detailed_results), 2)
        self.assertIn("exact_match", result.detailed_results[0][2])
        self.assertNotIn("execution_match", result.detailed_results[0][2])


if __name__ == "__main__":
    unittest.main()
