import time
import sys
from pathlib import Path

# This allows running the script directly from the repo root (e.g., `python src/app.py`)
# and ensures that package imports work correctly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.cfg import load_config
from src.utils.log import setup_logger
from loguru import logger

def main():
    """
    The main entrypoint for the application.
    """
    # --- Setup ---
    # Locate the configuration directory relative to this file.
    config_dir = Path(__file__).resolve().parent.parent / 'config'

    try:
        config = load_config(config_dir)
    except Exception as e:
        # Logger is not available yet, so we use a standard print.
        print(f"CRITICAL: Failed to load configuration from {config_dir}. Error: {e}")
        print("Please ensure 'config/default.yaml' is present and, if needed, 'config/secrets.yaml' is created from the example.")
        sys.exit(1)

    # With a valid config, we can now set up our logger.
    setup_logger(config.logging)

    logger.info("Bot application starting...")
    logger.info(f"Run mode: {'DRY RUN' if config.general.dry_run else 'LIVE'}")

    # --- Main Loop ---
    # This loop represents the bot's heartbeat, executing at the configured interval.
    while True:
        try:
            logger.info("--- New cycle starting ---")

            # The core logic from the plan will be built out here.
            # For now, these are placeholders.

            # 1. Ingest Data (e.g., market = ingestor.pull_all())
            # 2. Compute Analytics (e.g., risk_view = analytics.compute_risk(market))
            # 3. Update State (e.g., state.update(market, risk_view))
            # 4. Execute state-based actions (e.g., if state.mode == "ENTER": ...)
            # 5. Check risk guardrails

            logger.debug("Core logic (placeholders) executed successfully.")

            interval = config.general.poll_interval_seconds
            logger.info(f"Cycle finished. Sleeping for {interval} seconds.")
            time.sleep(interval)

        except KeyboardInterrupt:
            logger.warning("Shutdown signal received. Exiting gracefully.")
            break
        except Exception as e:
            logger.exception(f"An unexpected error occurred in the main loop: {e}")
            logger.error("The bot will rest for 60 seconds before retrying.")
            time.sleep(60)

if __name__ == "__main__":
    main()
