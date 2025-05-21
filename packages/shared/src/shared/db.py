from langchain_community.utilities import SQLDatabase
from shared.logger import get_logger
from sql_qa.config import get_app_config

app_config = get_app_config()

logger = get_logger(
    __name__,
    log_file=f"{app_config.logging.log_dir}/{__name__}.log",
    level=app_config.logging.level,
)

# MySQL connection string format: mysql+pymysql://username:password@host:port/database_name
conn = app_config.database.conn
logger.info(f"DB_CONN: {conn}")


def get_db():
    return SQLDatabase.from_uri(conn)


# db = get_db()

# logger.info(get_db.dialect)
# logger.info("First 10 tables: {}".format(db.get_usable_table_names()[:10]))

if __name__ == "__main__":
    get_db.run("SELECT * FROM Artist LIMIT 10;")
