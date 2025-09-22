from dataclasses import dataclass
from typing import Literal, Optional, List

from ..data.models import Option

import time
from loguru import logger

from ..data.delta_api import DeltaAPIClient
from ..utils.cfg import Config

@dataclass
class PlaceOrderAction:
    """
    A data class to represent the intent to place an order.
    This decouples the strategy logic from the broker execution logic.
    """
    product_id: int
    symbol: str
    side: Literal["buy", "sell"]
    size: int
    order_type: Literal["limit", "market"]
    limit_price: Optional[float] = None
    client_order_id: Optional[str] = None  # To be added by the execution layer for idempotency

from ..data.models import Position

@dataclass
class CloseOrderAction:
    """A data class to represent the intent to close an existing position."""
    position_to_close: Position
    reason: str  # e.g., "stop_loss" or "take_profit"

@dataclass
class RollOrderAction:
    """
    A data class to represent the intent to roll a position,
    which involves closing one position and opening another.
    """
    position_to_close: Position
    new_order_to_open: PlaceOrderAction
    reason: str # e.g., "threatened"

class OrderBroker:
    """
    Handles the execution of order-related actions by interacting with the API client.
    """
    def __init__(self, client: DeltaAPIClient, config: Config):
        self.client = client
        self.config = config
        logger.info("OrderBroker initialized.")

    def _generate_client_order_id(self, action: PlaceOrderAction) -> str:
        """Generates a unique, idempotent client order ID."""
        # e.g., dwb_sell_C-BTC-50000-251024_1666656000000
        return f"dwb_{action.side}_{action.symbol}_{int(time.time() * 1000)}"

    def execute_place_order_actions(self, actions: List[PlaceOrderAction]):
        """
        Executes a list of PlaceOrderAction intents.
        """
        if self.config.general.dry_run:
            logger.warning(f"[DRY RUN] Would have executed {len(actions)} order(s).")
            for action in actions:
                logger.info(f"[DRY RUN] Place Order: {action}")
            return

        logger.info(f"Executing {len(actions)} order action(s)...")
        for action in actions:
            client_oid = self._generate_client_order_id(action)
            logger.info(f"Placing order with client_order_id: {client_oid}")

            try:
                result = self.client.place_order(
                    product_id=action.product_id,
                    size=action.size,
                    side=action.side,
                    order_type=action.order_type,
                    limit_price=action.limit_price,
                    client_order_id=client_oid
                )
                if result:
                    logger.success(f"Successfully placed order for {action.symbol}. Response: {result}")
                else:
                    logger.error(f"Failed to place order for {action.symbol}. No result returned from API client.")
            except Exception as e:
                logger.exception(f"An exception occurred while placing order for {action.symbol}.")

    def execute_close_order_actions(self, actions: List[CloseOrderAction]):
        """
        Executes a list of CloseOrderAction intents by placing closing market orders.
        """
        if self.config.general.dry_run:
            logger.warning(f"[DRY RUN] Would have executed {len(actions)} closing order(s).")
            for action in actions:
                logger.info(f"[DRY RUN] Close Position: {action.position_to_close.symbol} due to {action.reason}")
            return

        logger.info(f"Executing {len(actions)} closing order action(s)...")
        for action in actions:
            position = action.position_to_close

            # Determine side and size for the closing order
            closing_side = "buy" if position.size < 0 else "sell"
            closing_size = abs(position.size)

            client_oid = f"dwb_close_{action.reason}_{position.symbol}_{int(time.time() * 1000)}"
            logger.info(f"Placing closing ({closing_side}) market order for {position.symbol} with client_order_id: {client_oid}")

            try:
                result = self.client.place_order(
                    product_id=position.instrument_id,
                    size=int(closing_size), # Ensure size is an integer
                    side=closing_side,
                    order_type="market" # Use market order to ensure the position is closed
                )
                if result:
                    logger.success(f"Successfully placed closing order for {position.symbol}. Response: {result}")
                else:
                    logger.error(f"Failed to place closing order for {position.symbol}. No result returned.")
            except Exception as e:
                logger.exception(f"An exception occurred while placing closing order for {position.symbol}.")

    def execute_roll_order_actions(self, actions: List[RollOrderAction]):
        """
        Executes a list of RollOrderAction intents.
        This is a critical operation that closes one position and opens another.
        """
        if self.config.general.dry_run:
            logger.warning(f"[DRY RUN] Would have executed {len(actions)} roll action(s).")
            for action in actions:
                logger.info(f"[DRY RUN] Roll Position: Close {action.position_to_close.symbol}, Open {action.new_order_to_open.symbol}")
            return

        logger.info(f"Executing {len(actions)} roll action(s)...")
        for action in actions:
            # --- 1. Close the old position with a market order ---
            position_to_close = action.position_to_close
            close_side = "buy" if position_to_close.size < 0 else "sell"
            close_size = abs(position_to_close.size)
            close_client_oid = f"dwb_roll_close_{position_to_close.symbol}_{int(time.time() * 1000)}"

            logger.info(f"Rolling Part 1: Placing closing market order for {position_to_close.symbol}")
            try:
                close_result = self.client.place_order(
                    product_id=position_to_close.instrument_id,
                    size=int(close_size),
                    side=close_side,
                    order_type="market",
                    client_order_id=close_client_oid
                )
                if not close_result:
                    logger.error(f"Failed to place closing order for roll of {position_to_close.symbol}. Aborting roll.")
                    continue # Skip to the next action
                logger.success(f"Closing order placed for {position_to_close.symbol}.")
            except Exception as e:
                logger.exception(f"Exception during closing part of roll for {position_to_close.symbol}. Aborting roll.")
                continue

            # --- 2. Open the new position with a limit order ---
            # In a real scenario, we might wait for fill confirmation here. For now, we proceed immediately.
            new_order_action = action.new_order_to_open
            open_client_oid = self._generate_client_order_id(new_order_action)

            logger.info(f"Rolling Part 2: Placing opening limit order for {new_order_action.symbol}")
            try:
                open_result = self.client.place_order(
                    product_id=new_order_action.product_id,
                    size=new_order_action.size,
                    side=new_order_action.side,
                    order_type=new_order_action.order_type,
                    limit_price=new_order_action.limit_price,
                    client_order_id=open_client_oid
                )
                if open_result:
                    logger.success(f"Successfully placed opening order for roll to {new_order_action.symbol}.")
                else:
                    logger.error(f"Failed to place opening order for roll to {new_order_action.symbol}.")
            except Exception as e:
                logger.exception(f"Exception during opening part of roll to {new_order_action.symbol}.")
