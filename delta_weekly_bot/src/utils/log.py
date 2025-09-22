import sys
from pathlib import Path
from loguru import logger

# Use a relative import to get the config model
from .cfg import LoggingConfig

def setup_logger(config: LoggingConfig):
    """
    Configures the Loguru logger based on the application's configuration.

    This function sets up two log handlers:
    1. A human-readable logger to the console (stderr).
    2. A structured JSON logger to a file, if enabled in the config.
    """
    logger.remove()  # Remove the default handler to ensure clean configuration

    # Configure the console logger
    logger.add(
        sys.stderr,
        level=config.level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
        ),
        colorize=True,
    )

    # Configure the file logger for structured JSON output if enabled
    if config.to_file:
        log_file_path = Path(config.file_path)

        # Ensure the parent directory for the log file exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file_path,
            level=config.level.upper(),
            serialize=True,  # This enables structured logging in JSON format
            rotation="10 MB",
            retention="10 days",
            catch=True,      # Catches exceptions from other modules and logs them
        )
        logger.info(f"Structured JSON logging is enabled. Log file: {log_file_path}")

    return logger
