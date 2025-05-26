import logging
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

# Global main logger instance
_main_logger = None


def get_timestamped_log_file(log_dir: str, prefix: str = "run") -> str:
    """
    Generate a timestamped log file path.

    Args:
        log_dir: Directory where log files will be stored
        prefix: Prefix for the log file name (default: "run")

    Returns:
        str: Path to the log file with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path(log_dir) / f"{prefix}_{timestamp}.log")


def get_main_logger(
    name: str = "main",
    level: Optional[int] = None,
    log_file: Optional[str] = "./logs/",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB default
    backup_count: int = 5,  # Keep 5 backup files by default
) -> logging.Logger:
    """
    Get or create the main logger instance.

    Args:
        name: The name of the main logger (default: "main")
        level: Optional logging level. If not provided, uses INFO level
        log_file: Path to log file or directory. If directory is provided,
                 a timestamped log file will be created in that directory.
                 If a specific file path is provided, that exact file will be used.
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        logging.Logger: The main logger instance
    """
    global _main_logger
    if _main_logger is None:
        _main_logger = get_logger(
            name=name,
            level=level,
            log_file=log_file,
            max_bytes=max_bytes,
            backup_count=backup_count,
            propagate=False,  # Main logger should not propagate to root
        )
    return _main_logger


def get_logger(
    name: str,
    level: Optional[int] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB default
    backup_count: int = 5,  # Keep 5 backup files by default
    propagate: bool = True,  # Whether to propagate to main logger
    use_console: bool = True,  # Whether to use console handler
) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger (typically __name__ of the calling module)
        level: Optional logging level. If not provided, uses INFO level
        log_file: Optional path to log file or directory. If directory is provided,
                 a timestamped log file will be created in that directory.
                 If a specific file path is provided, that exact file will be used.
        max_bytes: Maximum size of each log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        propagate: Whether to propagate logs to the main logger (default: True)
        use_console: Whether to use console handler (default: True)

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)

    # If logger already has handlers, return it to avoid duplicate handlers
    if logger.handlers:
        return logger

    # Set default level if not provided
    if level is None:
        level = logging.INFO

    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create console handler with formatting
    if use_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if log_file is provided
    if log_file:
        log_path = Path(log_file)

        # Create parent directory if it doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # If path ends with / or \, use timestamped file
        if log_path.is_dir() or str(log_path).endswith(("/", "\\")):
            log_file = get_timestamped_log_file(str(log_path), prefix=name)

        # Use RotatingFileHandler instead of FileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Set up propagation to main logger
    if propagate:
        main_logger = get_main_logger()
        # Only set up propagation if this is not the main logger itself
        if logger.name != main_logger.name:
            logger.propagate = True
            # Ensure the logger hierarchy is properly set up
            if not logger.parent or logger.parent.name != main_logger.name:
                logger.parent = main_logger
    else:
        logger.propagate = False

    return logger


class TurnLogger:
    delimiter = (
        "\t"  # Using tab as delimiter which is less likely to appear in text content
    )

    def __init__(self, csv_file_path):
        import os
        from collections import OrderedDict

        print(f"csv_file_path: {os.path.abspath(csv_file_path)}")
        self.csv_file_path = csv_file_path
        self.current_row = {}
        self.fieldnames = OrderedDict()  # Use OrderedDict to preserve field order
        self._ensure_csv_exists()

    def _ensure_csv_exists(self):
        try:
            if not os.path.exists(self.csv_file_path):
                with open(
                    self.csv_file_path, "w", newline="", encoding="utf-8"
                ) as csvfile:
                    writer = csv.DictWriter(
                        csvfile,
                        fieldnames=["created_date"],
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
                        self.fieldnames = OrderedDict.fromkeys(reader.fieldnames)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CSV file: {e}")

    def new_turn(self):
        """
        Start a new turn by saving the current turn (if any) and initializing a new one.
        """
        if self.current_row:
            self.save_turn()
        self.current_row = {
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def log(self, key, value):
        """
        Log a key-value pair. If the key already exists, append the new value with a line break.

        Args:
            key: The key to log
            value: The value to log
        """
        try:
            if key in self.current_row:
                self.current_row[key] = f"{self.current_row[key]}\n{value}"
            else:
                self.current_row[key] = value
                if key not in self.fieldnames:
                    self.fieldnames[key] = None
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
                    writer = csv.DictWriter(
                        temp_file,
                        fieldnames=list(self.fieldnames.keys()),
                        delimiter=self.delimiter,
                        quoting=csv.QUOTE_ALL,
                    )
                    writer.writeheader()

                    # Copy existing rows
                    for row in reader:
                        writer.writerow(row)

                # Get the temporary file path
                temp_path = temp_file.name

            # Replace original file with temporary file
            shutil.move(temp_path, self.csv_file_path)
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
                writer = csv.DictWriter(
                    csvfile,
                    fieldnames=list(self.fieldnames.keys()),
                    delimiter=self.delimiter,
                    quoting=csv.QUOTE_ALL,
                )
                writer.writerow(self.current_row)
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

    turn_logger = TurnLogger("turn_log.csv")
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
