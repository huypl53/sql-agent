from enum import Enum
from typing import Optional, Union
import sqlglot
from sql_qa.metrics.process_sql import Schema, get_sql

# Flag to disable value evaluation
DISABLE_VALUE = True
# Flag to disable distinct in select evaluation
DISABLE_DISTINCT = True


CLAUSE_KEYWORDS = (
    "select",
    "from",
    "where",
    "group",
    "order",
    "limit",
    "intersect",
    "union",
    "except",
)
JOIN_KEYWORDS = ("join", "on", "as")

WHERE_OPS = (
    "not",
    "between",
    "=",
    ">",
    "<",
    ">=",
    "<=",
    "!=",
    "in",
    "like",
    "is",
    "exists",
)
UNIT_OPS = ("none", "-", "+", "*", "/")
AGG_OPS = ("none", "max", "min", "count", "sum", "avg")
TABLE_TYPE = {
    "sql": "sql",
    "table_unit": "table_unit",
}

COND_OPS = ("and", "or")
SQL_OPS = ("intersect", "union", "except")
ORDER_OPS = ("desc", "asc")


HARDNESS = {
    "component1": ("where", "group", "order", "limit", "join", "or", "like"),
    "component2": ("except", "union", "intersect"),
}


def condition_has_or(conds):
    return "or" in conds[1::2]


def condition_has_like(conds):
    return WHERE_OPS.index("like") in [cond_unit[1] for cond_unit in conds[::2]]


def condition_has_sql(conds):
    for cond_unit in conds[::2]:
        val1, val2 = cond_unit[3], cond_unit[4]
        if val1 is not None and type(val1) is dict:
            return True
        if val2 is not None and type(val2) is dict:
            return True
    return False


def val_has_op(val_unit):
    return val_unit[0] != UNIT_OPS.index("none")


def has_agg(unit):
    return unit[0] != AGG_OPS.index("none")


def accuracy(count, total):
    if count == total:
        return 1
    return 0


def recall(count, total):
    if count == total:
        return 1
    return 0


def F1(acc, rec):
    if (acc + rec) == 0:
        return 0
    return (2.0 * acc * rec) / (acc + rec)


def get_scores(count, pred_total, label_total):
    if pred_total != label_total:
        return 0, 0, 0
    elif count == pred_total:
        return 1, 1, 1
    return 0, 0, 0


def eval_sel(pred, label):
    pred_sel = pred["select"][1]
    label_sel = label["select"][1]
    label_wo_agg = [unit[1] for unit in label_sel]
    pred_total = len(pred_sel)
    label_total = len(label_sel)
    cnt = 0
    cnt_wo_agg = 0

    for unit in pred_sel:
        if unit in label_sel:
            cnt += 1
            label_sel.remove(unit)
        if unit[1] in label_wo_agg:
            cnt_wo_agg += 1
            label_wo_agg.remove(unit[1])

    return label_total, pred_total, cnt, cnt_wo_agg


def eval_where(pred, label):
    pred_conds = [unit for unit in pred["where"][::2]]
    label_conds = [unit for unit in label["where"][::2]]
    label_wo_agg = [unit[2] for unit in label_conds]
    pred_total = len(pred_conds)
    label_total = len(label_conds)
    cnt = 0
    cnt_wo_agg = 0

    for unit in pred_conds:
        if unit in label_conds:
            cnt += 1
            label_conds.remove(unit)
        if unit[2] in label_wo_agg:
            cnt_wo_agg += 1
            label_wo_agg.remove(unit[2])

    return label_total, pred_total, cnt, cnt_wo_agg


def eval_group(pred, label):
    pred_cols = [unit[1] for unit in pred["groupBy"]]
    label_cols = [unit[1] for unit in label["groupBy"]]
    pred_total = len(pred_cols)
    label_total = len(label_cols)
    cnt = 0
    pred_cols = [pred.split(".")[1] if "." in pred else pred for pred in pred_cols]
    label_cols = [
        label.split(".")[1] if "." in label else label for label in label_cols
    ]
    for col in pred_cols:
        if col in label_cols:
            cnt += 1
            label_cols.remove(col)
    return label_total, pred_total, cnt


def eval_having(pred, label):
    pred_total = label_total = cnt = 0
    if len(pred["groupBy"]) > 0:
        pred_total = 1
    if len(label["groupBy"]) > 0:
        label_total = 1

    pred_cols = [unit[1] for unit in pred["groupBy"]]
    label_cols = [unit[1] for unit in label["groupBy"]]
    if (
        pred_total == label_total == 1
        and pred_cols == label_cols
        and pred["having"] == label["having"]
    ):
        cnt = 1

    return label_total, pred_total, cnt


def eval_order(pred, label):
    pred_total = label_total = cnt = 0
    if len(pred["orderBy"]) > 0:
        pred_total = 1
    if len(label["orderBy"]) > 0:
        label_total = 1
    if (
        len(label["orderBy"]) > 0
        and pred["orderBy"] == label["orderBy"]
        and (
            (pred["limit"] is None and label["limit"] is None)
            or (pred["limit"] is not None and label["limit"] is not None)
        )
    ):
        cnt = 1
    return label_total, pred_total, cnt


def eval_and_or(pred, label):
    pred_ao = pred["where"][1::2]
    label_ao = label["where"][1::2]
    pred_ao = set(pred_ao)
    label_ao = set(label_ao)

    if pred_ao == label_ao:
        return 1, 1, 1
    return len(pred_ao), len(label_ao), 0


def get_nestedSQL(sql):
    nested = []
    for cond_unit in sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]:
        if type(cond_unit[3]) is dict:
            nested.append(cond_unit[3])
        if type(cond_unit[4]) is dict:
            nested.append(cond_unit[4])
    if sql["intersect"] is not None:
        nested.append(sql["intersect"])
    if sql["except"] is not None:
        nested.append(sql["except"])
    if sql["union"] is not None:
        nested.append(sql["union"])
    return nested


def eval_nested(pred, label):
    label_total = 0
    pred_total = 0
    cnt = 0
    if pred is not None:
        pred_total += 1
    if label is not None:
        label_total += 1
    if pred is not None and label is not None:
        cnt += eval_exact_match(pred, label)
    return label_total, pred_total, cnt


def eval_IUEN(pred, label):
    lt1, pt1, cnt1 = eval_nested(pred["intersect"], label["intersect"])
    lt2, pt2, cnt2 = eval_nested(pred["except"], label["except"])
    lt3, pt3, cnt3 = eval_nested(pred["union"], label["union"])
    label_total = lt1 + lt2 + lt3
    pred_total = pt1 + pt2 + pt3
    cnt = cnt1 + cnt2 + cnt3
    return label_total, pred_total, cnt


def get_keywords(sql):
    res = set()
    if len(sql["where"]) > 0:
        res.add("where")
    if len(sql["groupBy"]) > 0:
        res.add("group")
    if len(sql["having"]) > 0:
        res.add("having")
    if len(sql["orderBy"]) > 0:
        res.add(sql["orderBy"][0])
        res.add("order")
    if sql["limit"] is not None:
        res.add("limit")
    if sql["except"] is not None:
        res.add("except")
    if sql["union"] is not None:
        res.add("union")
    if sql["intersect"] is not None:
        res.add("intersect")

    # or keyword
    ao = sql["from"]["conds"][1::2] + sql["where"][1::2] + sql["having"][1::2]
    if len([token for token in ao if token == "or"]) > 0:
        res.add("or")

    cond_units = sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]
    # not keyword
    if len([cond_unit for cond_unit in cond_units if cond_unit[0]]) > 0:
        res.add("not")

    # in keyword
    if (
        len(
            [
                cond_unit
                for cond_unit in cond_units
                if cond_unit[1] == WHERE_OPS.index("in")
            ]
        )
        > 0
    ):
        res.add("in")

    # like keyword
    if (
        len(
            [
                cond_unit
                for cond_unit in cond_units
                if cond_unit[1] == WHERE_OPS.index("like")
            ]
        )
        > 0
    ):
        res.add("like")

    return res


def eval_keywords(pred, label):
    pred_keywords = get_keywords(pred)
    label_keywords = get_keywords(label)
    pred_total = len(pred_keywords)
    label_total = len(label_keywords)
    cnt = 0

    for k in pred_keywords:
        if k in label_keywords:
            cnt += 1
    return label_total, pred_total, cnt


def count_agg(units):
    return len([unit for unit in units if has_agg(unit)])


def count_component1(sql):
    count = 0
    if len(sql["where"]) > 0:
        count += 1
    if len(sql["groupBy"]) > 0:
        count += 1
    if len(sql["orderBy"]) > 0:
        count += 1
    if sql["limit"] is not None:
        count += 1
    if len(sql["from"]["table_units"]) > 0:  # JOIN
        count += len(sql["from"]["table_units"]) - 1

    ao = sql["from"]["conds"][1::2] + sql["where"][1::2] + sql["having"][1::2]
    count += len([token for token in ao if token == "or"])
    cond_units = sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]
    count += len(
        [
            cond_unit
            for cond_unit in cond_units
            if cond_unit[1] == WHERE_OPS.index("like")
        ]
    )

    return count


def count_component2(sql):
    nested = get_nestedSQL(sql)
    return len(nested)


def count_others(sql):
    count = 0
    # number of aggregation
    agg_count = count_agg(sql["select"][1])
    agg_count += count_agg(sql["where"][::2])
    agg_count += count_agg(sql["groupBy"])
    if len(sql["orderBy"]) > 0:
        agg_count += count_agg(
            [unit[1] for unit in sql["orderBy"][1] if unit[1]]
            + [unit[2] for unit in sql["orderBy"][1] if unit[2]]
        )
    agg_count += count_agg(sql["having"])
    if agg_count > 1:
        count += 1

    # number of select columns
    if len(sql["select"][1]) > 1:
        count += 1

    # number of where conditions
    if len(sql["where"]) > 1:
        count += 1

    # number of group by clauses
    if len(sql["groupBy"]) > 1:
        count += 1

    return count


# class SqliteEvaluator:
#     """A simple evaluator"""
#     def __init__(self):
#         self.partial_scores = None


class EHardness(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXTRA = "extra"


def eval_hardness(sql) -> EHardness:
    """
    Evaluate the hardness level of a SQL query.

    The hardness score is determined based on three main components:
      1. Component 1: The number of SQL clauses and logical operators such as WHERE, GROUP BY, ORDER BY, LIMIT, JOIN, OR, and LIKE.
      2. Component 2: The number of nested SQL queries (subqueries using INTERSECT, UNION, EXCEPT).
      3. Others: The complexity of aggregations, number of select columns, where conditions, and group by clauses.

    The function uses the following logic:
      - "easy": Simple queries with at most one main clause, no subqueries, and no extra complexity.
      - "medium": Slightly more complex queries with up to two extra components, but still no subqueries.
      - "hard": Queries with more components or limited subquery usage.
      - "extra": All other queries, typically with multiple subqueries or high complexity.

    Args:
        sql (dict): The parsed SQL query in dictionary form.

    Returns:
        str: One of "easy", "medium", "hard", or "extra" indicating the query's hardness.

    Example:
        >>> sql = {...}  # parsed SQL dict
        >>> level = eval_hardness(sql)
        >>> print(level)
        'medium'
    """
    count_comp1_ = count_component1(sql)
    count_comp2_ = count_component2(sql)
    count_others_ = count_others(sql)

    if count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ == 0:
        return EHardness.EASY
    elif (count_others_ <= 2 and count_comp1_ <= 1 and count_comp2_ == 0) or (
        count_comp1_ <= 2 and count_others_ < 2 and count_comp2_ == 0
    ):
        return EHardness.MEDIUM
    elif (
        (count_others_ > 2 and count_comp1_ <= 2 and count_comp2_ == 0)
        or (2 < count_comp1_ <= 3 and count_others_ <= 2 and count_comp2_ == 0)
        or (count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ <= 1)
    ):
        return EHardness.HARD
    else:
        return EHardness.EXTRA


def eval_exact_match(pred, label):
    partial_scores = eval_partial_match(pred, label)

    for key, score in partial_scores.items():
        if score["f1"] != 1:
            return 0

    if len(label["from"]["table_units"]) > 0:
        label_tables = sorted(label["from"]["table_units"])
        pred_tables = sorted(pred["from"]["table_units"])
        return label_tables == pred_tables
    return 1


def eval_partial_match(pred, label):
    res = {}

    label_total, pred_total, cnt, cnt_wo_agg = eval_sel(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["select"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }
    acc, rec, f1 = get_scores(cnt_wo_agg, pred_total, label_total)
    res["select(no AGG)"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt, cnt_wo_agg = eval_where(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["where"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }
    acc, rec, f1 = get_scores(cnt_wo_agg, pred_total, label_total)
    res["where(no OP)"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt = eval_group(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["group(no Having)"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt = eval_having(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["group"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt = eval_order(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["order"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt = eval_and_or(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["and/or"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt = eval_IUEN(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["IUEN"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    label_total, pred_total, cnt = eval_keywords(pred, label)
    acc, rec, f1 = get_scores(cnt, pred_total, label_total)
    res["keywords"] = {
        "acc": acc,
        "rec": rec,
        "f1": f1,
        "label_total": label_total,
        "pred_total": pred_total,
    }

    return res


def normalize_sql_str(sql_str):
    return sqlglot.transpile(sql_str, write="", pretty=True)[0]


class Evaluator:
    """
    A simple evaluator for SQL queries that evaluates the hardness of a SQL query.
    It uses the eval_hardness function to determine the hardness level of the query.
    """

    def __init__(self, schema: Union[dict, Schema] | None = None):
        if isinstance(schema, dict):
            schema = Schema(schema)
        self.schema = schema
        pass

    def eval_raw_sql_hardness(self, sql_str: str) -> EHardness:
        """
        Evaluate the hardness of a SQL query.

        Args:
            sql (dict): The parsed SQL query in dictionary form.

        Returns:
            str: The hardness level of the SQL query.
        """
        sql_str = normalize_sql_str(sql_str)
        sql = get_sql(self.schema, sql_str)

        return eval_hardness(sql)
