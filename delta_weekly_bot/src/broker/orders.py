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
