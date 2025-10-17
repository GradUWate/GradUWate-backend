
import logging
import sys


def configure_logging() -> None:
    """Configure basic console logging if not already set."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
