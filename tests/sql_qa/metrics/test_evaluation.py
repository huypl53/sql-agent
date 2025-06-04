import pytest
from src.sql_qa.metrics.util import eval_hardness, EHardness, Evaluator

@pytest.mark.parametrize(
    "sql,expected",
    [
        # Easy: 1 main clause, no subqueries, no extra complexity
        (
            {
                "select": (False, [("none", "name")]),
                "from": {"table_units": ["users"], "conds": []},
                "where": [],
                "groupBy": [],
                "having": [],
                "orderBy": [],
                "limit": None,
                "intersect": None,
                "union": None,
                "except": None,
            },
            EHardness.EASY,
        ),
        # Medium: 1 main clause, 1 extra component (multiple select columns)
        (
            {
                "select": (False, [("none", "name"), ("none", "age")]),
                "from": {"table_units": ["users"], "conds": []},
                "where": [],
                "groupBy": [],
                "having": [],
                "orderBy": [],
                "limit": None,
                "intersect": None,
                "union": None,
                "except": None,
            },
            EHardness.MEDIUM,
        ),
        # Hard: 3 main clauses, no subqueries, 1 extra component
        (
            {
                "select": (False, [("none", "name")]),
                "from": {"table_units": ["users", "orders"], "conds": []},
                "where": [("none", "=", "age", 25, None)],
                "groupBy": [],
                "having": [],
                "orderBy": [],
                "limit": None,
                "intersect": None,
                "union": None,
                "except": None,
            },
            EHardness.MEDIUM,
        ),
        # Extra: subquery present
        (
            {
                "select": (False, [("none", "name")]),
                "from": {"table_units": ["users"], "conds": []},
                "where": [],
                "groupBy": [],
                "having": [],
                "orderBy": [],
                "limit": None,
                "intersect": {
                    "select": (False, [("none", "id")]),
                    "from": {"table_units": ["orders"], "conds": []},
                    "where": [],
                    "groupBy": [],
                    "having": [],
                    "orderBy": [],
                    "limit": None,
                    "intersect": None,
                    "union": None,
                    "except": None,
                },
                "union": None,
                "except": None,
            },
            EHardness.HARD,
        ),
    ],
)
def test_eval_hardness(sql, expected):
    assert eval_hardness(sql) == expected


@pytest.mark.parametrize(
    "sql_str,schema,expected",
    [
        (
            "SELECT name FROM users WHERE age = 25",
            {"users": ["name", "age"]},
            EHardness.EASY,
        ),
        (
            "SELECT name, age FROM users WHERE age > 30",
            {"users": ["name", "age"]},
            EHardness.MEDIUM,
        ),
        (
            "SELECT name FROM users JOIN orders ON users.id = orders.user_id",
            {"users": ["id", "name"], "orders": ["user_id"]},
            EHardness.EASY,
        ),
        (
            "SELECT name FROM users WHERE id IN (SELECT user_id FROM orders WHERE amount > 100)",
            {"users": ["id", "name"], "orders": ["user_id", "amount"]},
            EHardness.HARD,
        ),
        (
            'SELECT * FROM FLIGHTS AS T1 JOIN AIRPORTS AS T2 ON T1.SourceAirport  =  T2.AirportCode WHERE T2.City  =  "Aberdeen"',
            {"flights": ["sourceairport"], "airports": ["city", "airportcode"]},
            EHardness.MEDIUM,
        ),
    ],
)
def test_eval_raw_sql_hardness(sql_str, schema, expected):
    """
    Test the eval_hardness function with raw SQL strings.
    """
    evaluator = Evaluator(schema=schema)
    assert (
        evaluator.eval_raw_sql_hardness(sql_str) == expected
    )  # Adjust expected value based on actual SQL structure
