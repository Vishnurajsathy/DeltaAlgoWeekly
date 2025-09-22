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
