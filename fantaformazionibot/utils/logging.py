import logging


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    # Set higher logging level for specific libraries if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str=__name__) -> logging.Logger:
    return logging.getLogger(name)