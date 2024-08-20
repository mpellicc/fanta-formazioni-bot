import logging
from typing import Optional


def setup_logging() -> None:
    """
    Configures the logging module to output logs in a standardized format.

    Sets the logging level to INFO and configures the logging format to include
    the timestamp, logger name, log level, and log message.

    Additionally, sets the logging level for the 'httpx' library to WARNING.
    """
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    # Set higher logging level for specific libraries if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(file_name: str, class_name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for the given file name and class name.
    
    This function creates a logger instance for the given file name and class name. If the class name is not provided,
    the file name is used as the logger name. The logger instance is obtained using the `logging.getLogger` function.

    Args:
        file_name (str): The name of the file.
        class_name (Optional[str], optional): The name of the class. Defaults to None.

    Returns:
        logging.Logger: The logger instance for the given file name and class name.
    """
    if class_name is None:
        name = file_name.rstrip(".")
    else:
        name = f"{file_name}.{class_name}"
    return logging.getLogger(name)
