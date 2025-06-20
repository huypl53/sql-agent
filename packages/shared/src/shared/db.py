from langchain_community.utilities import SQLDatabase
from shared.logger import logger
from sql_qa.config import get_app_config
from typing import Any, Tuple

app_config = get_app_config()


# MySQL connection string format: mysql+pymysql://username:password@host:port/database_name
conn = app_config.database.conn
logger.info(f"DB_CONN: {conn}")


def get_db():
    return SQLDatabase.from_uri(conn)


def execute_sql(db: SQLDatabase, sql: str) -> Tuple[Any, bool]:
    """
    Return:
        execution_result [Any]
        is_success [bool]
    """
    try:
        execution_result = db.run(sql)
        return execution_result, True
    except Exception as e:
        return str(e), False


# db = get_db()

# logger.info(get_db.dialect)
# logger.info("First 10 tables: {}".format(db.get_usable_table_names()[:10]))

if __name__ == "__main__":
    get_db().run("SELECT * FROM Artist LIMIT 10;")
