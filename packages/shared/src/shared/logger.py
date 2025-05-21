import logging
import sys
from typing import Optional
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


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


def get_logger(
    name: str,
    level: Optional[int] = None,
    log_file: Optional[str] = "./logs/",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB default
    backup_count: int = 5,  # Keep 5 backup files by default
) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger (typically __name__ of the calling module)
        level: Optional logging level. If not provided, uses INFO level
        log_file: Optional path to log file or directory. If directory is provided,
                 a timestamped log file will be created in that directory
        max_bytes: Maximum size of each log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.propagate = False  # Prevent propagation to parent loggers

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
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if log_file is provided
    if log_file:
        # If log_file is a directory, create a timestamped log file
        log_path = Path(log_file)
        if (
            log_path.is_dir()
            or str(log_path).endswith("/")
            or str(log_path).endswith("\\")
        ):
            log_path.mkdir(parents=True, exist_ok=True)
            log_file = get_timestamped_log_file(str(log_path), prefix=name)
        else:
            # Create parent directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use RotatingFileHandler instead of FileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Example usage:
if __name__ == "__main__":
    # Example with timestamped log file in logs directory
    logger = get_logger(__name__, log_file="logs")
    logger.info("Logger initialized successfully")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
