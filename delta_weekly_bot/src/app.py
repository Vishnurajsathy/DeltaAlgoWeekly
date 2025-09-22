import time
import sys
from pathlib import Path

# This allows running the script directly from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.utils.cfg import load_config
from src.utils.log import setup_logger
from src.data.delta_api import DeltaAPIClient
from src.data.ingestor import DataIngestor
from src.core.state import StateMachine, BotState
from src.strategy.rules import PrecheckRules
from src.strategy.engine import StrategyEngine
from src.broker.orders import OrderBroker

def main():
    """
    The main entrypoint for the application.
    """
    # --- Setup ---
    config_dir = Path(__file__).resolve().parent.parent / 'config'

    try:
        config = load_config(config_dir)
    except Exception as e:
        print(f"CRITICAL: Failed to load configuration. {e}")
        sys.exit(1)

    setup_logger(config.logging)

    # TODO: Move base_url into the main configuration file.
    base_url = "https://testnet-api.delta.exchange"
    if "india" in config.general.timezone.lower():
        base_url = "https://cdn-ind.testnet.deltaex.org"

    logger.info("Bot application starting...")
    logger.info(f"Run mode: {'DRY RUN' if config.general.dry_run else 'LIVE'}")

    # --- Initialize Core Components ---
    try:
        api_client = DeltaAPIClient(secrets=config.secrets.delta, base_url=base_url)
        ingestor = DataIngestor(client=api_client, config=config)
        state_machine = StateMachine(initial_state=BotState.PRECHECK)
        broker = OrderBroker(client=api_client, config=config)
        engine = StrategyEngine(config)
    except Exception as e:
        logger.exception(f"Failed to initialize core components: {e}")
        sys.exit(1)

    # --- Main Loop ---
    while state_machine.is_running:
        try:
            logger.info(f"--- Cycle start | State: {state_machine.state.name} ---")

            # 1. Ingest Data
            snapshot = ingestor.fetch_all()

            # 2. State-based Logic
            if state_machine.state == BotState.PRECHECK:
                rules = PrecheckRules(config, snapshot)
                if rules.are_all_checks_ok():
                    state_machine.transition(BotState.ENTER)
                else:
                    logger.warning("Pre-check rules failed. Moving to IDLE state for the next cycle.")
                    state_machine.transition(BotState.IDLE)

            elif state_machine.state == BotState.IDLE:
                logger.info("In IDLE state. Waiting for next cycle to re-check conditions.")
                state_machine.transition(BotState.PRECHECK)

            elif state_machine.state == BotState.ENTER:
                logger.info("In ENTER state, executing entry logic.")
                order_actions = engine.handle_enter_state(snapshot)

                if order_actions:
                    logger.info(f"Strategy engine generated {len(order_actions)} order action(s).")
                    broker.execute_place_order_actions(order_actions)
                    state_machine.transition(BotState.MONITOR)
                else:
                    logger.info("No new trade opportunities found. Returning to IDLE.")
                    state_machine.transition(BotState.IDLE)

            elif state_machine.state == BotState.MONITOR:
                logger.info("In MONITOR state. Checking open positions for SL/TP.")
                close_actions = engine.handle_monitor_state(snapshot)

                if close_actions:
                    logger.info(f"Strategy engine generated {len(close_actions)} closing action(s).")
                    broker.execute_close_order_actions(close_actions)
                    # After closing a leg, re-evaluate the whole state on the next cycle.
                    state_machine.transition(BotState.PRECHECK)
                elif not snapshot.positions:
                     logger.info("No open positions found. Returning to PRECHECK.")
                     state_machine.transition(BotState.PRECHECK)
                else:
                    logger.info(f"No actions needed for {len(snapshot.positions)} open position(s). Continuing to monitor.")
                    # Stay in MONITOR state


            # ... other states like ADJUST, HEDGE_ROLL will be added here ...

            # 3. Sleep until next cycle
            interval = config.general.poll_interval_seconds
            logger.info(f"Cycle finished. Sleeping for {interval} seconds.")
            time.sleep(interval)

        except KeyboardInterrupt:
            state_machine.stop()
            logger.warning("Shutdown signal received. Exiting gracefully.")
        except Exception as e:
            logger.exception(f"An unexpected error occurred in the main loop: {e}")
            logger.error("Resting for 60 seconds before retrying.")
            time.sleep(60)

if __name__ == "__main__":
    main()
