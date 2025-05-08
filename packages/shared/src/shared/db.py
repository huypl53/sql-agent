from langchain_community.utilities import SQLDatabase
from shared.logger import get_logger
import logging
import os
from dotenv import load_dotenv

load_dotenv(override=True, verbose=True)

logger = get_logger(__name__, logging.INFO)

# MySQL connection string format: mysql+pymysql://username:password@host:port/database_name
conn = os.environ.get("DB_CONN", None)
logger.info(f"DB_CONN: {conn}")
if not conn:
    conn = "sqlite:///Chinook.db"
    logger.warning(
        "No connection string provided in .env, use sample db {} instead".format(conn)
    )


db = SQLDatabase.from_uri(conn)

logger.info(db.dialect)
logger.info("First 10 tables: {}".format(db.get_usable_table_names()[:10]))

if __name__ == "__main__":
    db.run("SELECT * FROM Artist LIMIT 10;")
