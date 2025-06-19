import logging
import logging.handlers
import os.path
import sys
from datetime import datetime
import csv
import os
from functools import wraps
import tempfile
import shutil
import subprocess

_LOG_BASE_NAME = ""
csv.field_size_limit(sys.maxsize)
CSV_DEMILITER = "|"

def get_commit_hash():
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"
    except FileNotFoundError:
        return "git-not-found"


def get_short_commit_hash():
    """Get the short version of the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"
    except FileNotFoundError:
        return "git-not-found"


def get_commit_timestamp_basename():
    """Generate basename with commit hash and timestamp."""
    global _LOG_BASE_NAME
    if not _LOG_BASE_NAME:
        commit_hash = get_short_commit_hash()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOG_BASE_NAME = f"{commit_hash}_{timestamp}"
    return _LOG_BASE_NAME


def create_run_log_csv(csv_path="run_logs.csv"):
    """Create CSV file for tracking run logs and descriptions."""
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="") as f:
            import csv

            writer = csv.writer(f, delimiter=CSV_DEMILITER)
            writer.writerow(["logfile_basename", "description"])
    return csv_path


def setup_logger_with_commit_info(
    name="app",
    level=logging.INFO,
    log_dir="logs",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
):
    """Set up a logger that includes commit hash and timestamp-based filename."""

    # Get commit information and basename
    commit_hash = get_commit_hash()
    short_hash = get_short_commit_hash()
    basename = get_commit_timestamp_basename()

    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Create custom formatter
    class CommitFormatter(logging.Formatter):
        def format(self, record):
            # Add commit info to the record
            record.commit_hash = commit_hash
            record.short_hash = short_hash
            record.timestamp = datetime.now().isoformat()
            return super().format(record)

    # Set up logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = CommitFormatter(
        fmt="%(timestamp)s - %(name)s - %(levelname)s - [%(short_hash)s] - %(filename)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with commit_hash_timestamp basename
    log_filename = f"{basename}.log"
    log_filepath = os.path.join(log_dir, log_filename)
    file_handler = logging.handlers.RotatingFileHandler(
        log_filepath, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_formatter = CommitFormatter(
        fmt="%(timestamp)s - %(name)s - %(levelname)s - [%(short_hash)s] - %(filename)s:%(lineno)d %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Store info for reference

    setattr(logger, "basename", basename)
    return logger


def add_run_to_csv(basename, csv_path="run_logs.csv", description=""):
    """Add a new run entry to the CSV file."""
    with open(csv_path, "a", newline="") as f:
        import csv

        writer = csv.writer(f, delimiter=CSV_DEMILITER)
        writer.writerow([basename, description])


APP_NAME = "text2sql-bot"
LOG_DIR = "./logs/"
logger = setup_logger_with_commit_info(APP_NAME, log_dir=LOG_DIR)


class TurnLogger:
    delimiter = CSV_DEMILITER

    def __init__(
        self,
        csv_file_path=os.path.join(
            LOG_DIR,
            f"{get_commit_timestamp_basename()}_turn.csv",
        ),
        identity_columns=None,
    ):
        """
        Initialize TurnLogger with optional identity columns.

        Args:
            csv_file_path: Path to the CSV file
            identity_columns: List of column names that serve as identity columns.
                            If None, defaults to ["created_date"].
                            Can include "id" for auto-incrementing row numbers.
        """

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
                return result
            except Exception as e:
                turn_logger.log("error", f"Error: {e}")
                raise e
            finally:
                turn_logger.save_turn()

        return wrapper

    return decorator


# Create/update CSV tracking file
CSV_RUN_LOG_BASE = f"{get_short_commit_hash()}_run.csv"
CSV_RUN_LOG = os.path.join(LOG_DIR, CSV_RUN_LOG_BASE)

csv_path = create_run_log_csv(CSV_RUN_LOG)
run_log_basename = getattr(logger, "basename", CSV_RUN_LOG_BASE)

add_run_to_csv(run_log_basename, csv_path)

# Example usage:
if __name__ == "__main__":
    # Example with timestamped log file in logs directory
    # logger = get_logger(__name__, log_file="logs")
    logger.info("Logger initialized successfully")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    turn_logger = TurnLogger(identity_columns=["id"])

    @with_a_turn_logger(turn_logger)
    def run_with_turnlogger(i):
        # turn_logger.new_turn()
        turn_logger.log(f"key{i}", f"value{i}")
        turn_logger.log(f"key{i+1}", f"value{i}")
        # turn_logger.new_turn()

    for i in range(5):
        run_with_turnlogger(i)
