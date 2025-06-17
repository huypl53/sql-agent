from loguru import logger
import sys
from typing import Optional
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
import csv
import os
from functools import wraps
from collections import OrderedDict
import tempfile
import shutil

csv.field_size_limit(sys.maxsize)



# --- Loguru configuration ---
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

def configure_logger(
    log_file: Optional[str] = "./logs/",
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
):
    logger.remove()  # Remove default handler

    # Console handler
    logger.add(sys.stdout, level=level, format=LOG_FORMAT, enqueue=True, backtrace=True, diagnose=True)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.is_dir() or str(log_path).endswith(("/", "\\")):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = str(log_path / f"run_{timestamp}.log")
        logger.add(
            log_file,
            rotation=max_bytes,
            retention=backup_count,
            level=level,
            format=LOG_FORMAT,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

configure_logger(log_file="logs", level="INFO")

def get_main_logger(*args, **kwargs):
    return logger

def get_logger(*args, **kwargs):
    return logger

class TurnLogger:
    delimiter = (
        "\t"  # Using tab as delimiter which is less likely to appear in text content
    )

    def __init__(self, csv_file_path, identity_columns=None):
        """
        Initialize TurnLogger with optional identity columns.

        Args:
            csv_file_path: Path to the CSV file
            identity_columns: List of column names that serve as identity columns.
                            If None, defaults to ["created_date"].
                            Can include "id" for auto-incrementing row numbers.
        """
        import os
        from collections import OrderedDict

        print(f"csv_file_path: {os.path.abspath(csv_file_path)}")
        self.csv_file_path = csv_file_path
        self.current_row = {}
        self.identity_columns = identity_columns or ["created_date"]
        # Initialize fieldnames as a list to maintain order
        self.fieldnames = list(self.identity_columns)
        self._ensure_csv_exists()
        self._load_last_id()

    def _load_last_id(self):
        """Load the last used ID from the CSV file if it exists."""
        self.last_id = 0
        if os.path.exists(self.csv_file_path):
            try:
                with open(
                    self.csv_file_path, "r", newline="", encoding="utf-8"
                ) as csvfile:
                    reader = csv.DictReader(
                        csvfile, delimiter=self.delimiter, quoting=csv.QUOTE_ALL
                    )
                    for row in reader:
                        if "id" in row and row["id"].isdigit():
                            self.last_id = max(self.last_id, int(row["id"]))
            except Exception:
                pass  # If file is empty or corrupted, start from 0

    def _ensure_csv_exists(self):
        try:
            if not os.path.exists(self.csv_file_path):
                with open(
                    self.csv_file_path, "w", newline="", encoding="utf-8"
                ) as csvfile:
                    writer = csv.DictWriter(
                        csvfile,
                        fieldnames=self.fieldnames,
                        delimiter=self.delimiter,
                        quoting=csv.QUOTE_ALL,
                    )
                    writer.writeheader()
            else:
                # Read existing fieldnames to preserve order
                with open(
                    self.csv_file_path, "r", newline="", encoding="utf-8"
                ) as csvfile:
                    reader = csv.DictReader(
                        csvfile, delimiter=self.delimiter, quoting=csv.QUOTE_ALL
                    )
                    if reader.fieldnames:
                        # Ensure identity columns are first in the fieldnames
                        existing_fields = [
                            f
                            for f in reader.fieldnames
                            if f not in self.identity_columns
                        ]
                        self.fieldnames = self.identity_columns + existing_fields
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CSV file: {e}")

    def new_turn(self):
        """
        Start a new turn by saving the current turn (if any) and initializing a new one.
        """
        if self.current_row:
            self.save_turn()

        # Initialize identity columns
        self.current_row = {}
        for col in self.identity_columns:
            if col == "id":
                self.last_id += 1
                self.current_row[col] = str(self.last_id)
            elif col == "created_date":
                self.current_row[col] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                self.current_row[col] = ""  # Initialize other identity columns as empty

    def log(self, key, value):
        """
        Log a key-value pair. If the key already exists, append the new value with a line break.

        Args:
            key: The key to log
            value: The value to log
        """
        try:
            if key is None:
                raise ValueError("Cannot log with None key")

            if key in self.current_row:
                self.current_row[key] = f"{self.current_row[key]}\n{value}"
            else:
                self.current_row[key] = value
                if key not in self.fieldnames:
                    self.fieldnames.append(key)
                    self._update_csv_header()
        except Exception as e:
            raise RuntimeError(f"Failed to log key-value pair: {e}")

    def _update_csv_header(self):
        try:
            # Create a temporary file using tempfile module
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, newline="", encoding="utf-8"
            ) as temp_file:
                # Write to temporary file with new header
                with open(
                    self.csv_file_path, "r", newline="", encoding="utf-8"
                ) as infile:
                    reader = csv.DictReader(
                        infile, delimiter=self.delimiter, quoting=csv.QUOTE_ALL
                    )
                    # Get all existing fieldnames, filtering out None values
                    existing_fieldnames = [
                        f for f in (reader.fieldnames or []) if f is not None
                    ]
                    # Combine identity columns with existing fields, ensuring no duplicates
                    all_fieldnames = list(
                        dict.fromkeys(self.identity_columns + existing_fieldnames)
                    )
                    # Add any new fields that aren't in either list
                    all_fieldnames.extend(
                        [
                            f
                            for f in self.fieldnames
                            if f not in all_fieldnames and f is not None
                        ]
                    )

                    writer = csv.DictWriter(
                        temp_file,
                        fieldnames=all_fieldnames,
                        delimiter=self.delimiter,
                        quoting=csv.QUOTE_ALL,
                    )
                    writer.writeheader()

                    # Copy existing rows, ensuring all fields are present
                    for row in reader:
                        # Create a new row with all fields initialized to empty string
                        new_row = {field: "" for field in all_fieldnames}
                        # Update with existing values, filtering out None keys
                        new_row.update({k: v for k, v in row.items() if k is not None})
                        writer.writerow(new_row)

                # Get the temporary file path
                temp_path = temp_file.name

            # Replace original file with temporary file
            shutil.move(temp_path, self.csv_file_path)

            # Update our fieldnames to match the new header
            self.fieldnames = all_fieldnames
        except Exception as e:
            # Clean up temporary file if it exists
            if "temp_path" in locals() and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise RuntimeError(f"Failed to update CSV header: {e}")

    def save_turn(self):
        try:
            with open(self.csv_file_path, "a", newline="", encoding="utf-8") as csvfile:
                # Ensure all fields are present in the row and no None keys
                row = {field: "" for field in self.fieldnames}
                row.update({k: v for k, v in self.current_row.items() if k is not None})

                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=self.fieldnames,
                    delimiter=self.delimiter,
                    quoting=csv.QUOTE_ALL,
                )
                writer.writerow(row)
        except Exception as e:
            raise RuntimeError(f"Failed to save turn: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures the current turn is saved"""
        if self.current_row:
            self.save_turn()


def with_a_turn_logger(turn_logger: TurnLogger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            turn_logger.new_turn()
            try:
                result = func(*args, **kwargs)
                turn_logger.save_turn()
                return result
            except Exception as e:
                turn_logger.log("error", f"Error: {e}")
                turn_logger.save_turn()
                raise e

        return wrapper

    return decorator


# Example usage:
if __name__ == "__main__":
    # Example with timestamped log file in logs directory
    logger = get_logger(__name__, log_file="logs")
    logger.info("Logger initialized successfully")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    turn_logger = TurnLogger("turn_log_with_id_test.csv", identity_columns=["id"])
    turn_logger.new_turn()
    turn_logger.log("key1", "value1")
    turn_logger.log("key2", "value2")
    turn_logger.new_turn()
    turn_logger.log("key1", "value3")
    turn_logger.log("key3", "value4")
    turn_logger.new_turn()
    turn_logger.log("new_key1", "value5")
    turn_logger.log("new_key2", "value6")
    turn_logger.log("new_key3", "value8")
    turn_logger.new_turn()  # Final save
