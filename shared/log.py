import logging
from logging.handlers import RotatingFileHandler
from typing import Union
import colorama
import os


def setup_logging(loglevel: Union[int, str] = logging.INFO, *, silent: bool = False):
    """Configure file and console logging handlers for the current service.

    Args:
        loglevel: Numeric or textual logging level.
        silent: Skip the startup log line when `True`.
    """

    os.makedirs("logs", exist_ok=True)

    service = os.path.basename(os.getcwd())
    log_filename = f"logs/{service}.log"

    handler = RotatingFileHandler(log_filename, maxBytes=100000, backupCount=10)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # console
    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    numeric_level = (
        loglevel
        if isinstance(loglevel, int)
        else getattr(logging, loglevel.upper(), logging.INFO)
    )

    logging.basicConfig(
        level=numeric_level,
        format=f"{colorama.Fore.LIGHTBLACK_EX}%(asctime)s{colorama.Style.RESET_ALL} {colorama.Style.BRIGHT}%(levelname)s {colorama.Fore.LIGHTYELLOW_EX}[%(name)s]{colorama.Style.RESET_ALL} %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
        force=True,
        handlers=[handler, console],
    )
    logging.addLevelName(
        logging.DEBUG,
        f"{colorama.Fore.BLUE}{logging.getLevelName(logging.DEBUG)}{colorama.Style.RESET_ALL}",
    )
    logging.addLevelName(
        logging.INFO,
        f"{colorama.Fore.GREEN}{logging.getLevelName(logging.INFO)}{colorama.Style.RESET_ALL}",
    )
    logging.addLevelName(
        logging.WARNING,
        f"{colorama.Fore.YELLOW}{logging.getLevelName(logging.WARNING)}{colorama.Style.RESET_ALL}",
    )
    logging.addLevelName(
        logging.ERROR,
        f"{colorama.Fore.RED}{logging.getLevelName(logging.ERROR)}{colorama.Style.RESET_ALL}",
    )
    logging.addLevelName(
        logging.CRITICAL,
        f"{colorama.Fore.MAGENTA}{logging.getLevelName(logging.CRITICAL)}{colorama.Style.RESET_ALL}",
    )

    if not silent:
        logging.info(
            f"Logging initialized at {logging.getLevelName(numeric_level)} level"
        )


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""
    return logging.getLogger(name)
