import time
from dataclasses import dataclass
from typing import Literal, Optional, List

from loguru import logger

from ..data.models import Option, Position
from ..data.delta_api import DeltaAPIClient
from ..utils.cfg import Config
from ..data.stores import TradeJournal

@dataclass
class PlaceOrderAction:
    """A data class to represent the intent to place an order."""
    product_id: int
    symbol: str
    side: Literal["buy", "sell"]
    size: int
    order_type: Literal["limit", "market"]
    limit_price: Optional[float] = None
    client_order_id: Optional[str] = None

@dataclass
class CloseOrderAction:
    """A data class to represent the intent to close an existing position."""
    position_to_close: Position
    reason: str

@dataclass
class RollOrderAction:
    """A data class to represent the intent to roll a position."""
    position_to_close: Position
    new_order_to_open: PlaceOrderAction
    reason: str

class OrderBroker:
    """
    Handles the execution of order-related actions by interacting with the
    API client and journaling the results.
    """
    def __init__(self, client: DeltaAPIClient, config: Config, journal: TradeJournal):
        self.client = client
        self.config = config
        self.journal = journal
        logger.info("OrderBroker initialized.")

    def _generate_client_order_id(self, action: PlaceOrderAction) -> str:
        """Generates a unique, idempotent client order ID."""
        return f"dwb_{action.side}_{action.symbol}_{int(time.time() * 1000)}"

    def execute_place_order_actions(self, actions: List[PlaceOrderAction]):
        if self.config.general.dry_run:
            logger.warning(f"[DRY RUN] Would have placed {len(actions)} order(s).")
            for action in actions: logger.info(f"[DRY RUN] Place Order: {action}")
            return

        for action in actions:
            client_oid = self._generate_client_order_id(action)
            try:
                result = self.client.place_order(
                    product_id=action.product_id, size=action.size, side=action.side,
                    order_type=action.order_type, limit_price=action.limit_price, client_order_id=client_oid
                )
                if result:
                    logger.success(f"Successfully placed order for {action.symbol}. Response: {result}")
                    # Assume market orders fill at the returned price, limit orders might not have a fill price yet.
                    fill_price = float(result.get('avg_fill_price', action.limit_price or 0.0))
                    self.journal.record_trade(
                        symbol=action.symbol, side=action.side, size=action.size, price=fill_price
                    )
            except Exception:
                logger.exception(f"Exception placing order for {action.symbol}.")

    def execute_close_order_actions(self, actions: List[CloseOrderAction]):
        if self.config.general.dry_run:
            logger.warning(f"[DRY RUN] Would have closed {len(actions)} position(s).")
            for action in actions: logger.info(f"[DRY RUN] Close Position: {action.position_to_close.symbol}")
            return

        for action in actions:
            position = action.position_to_close
            closing_side = "buy" if position.size < 0 else "sell"
            closing_size = abs(position.size)
            client_oid = f"dwb_close_{action.reason}_{position.symbol}_{int(time.time() * 1000)}"
            try:
                result = self.client.place_order(
                    product_id=position.instrument_id, size=int(closing_size),
                    side=closing_side, order_type="market", client_order_id=client_oid
                )
                if result:
                    logger.success(f"Successfully placed closing order for {position.symbol}.")
                    exit_price = float(result.get('avg_fill_price', 0.0))
                    pnl = (position.entry_price - exit_price) * abs(position.size)
                    self.journal.record_trade(
                        symbol=position.symbol, side=closing_side, size=closing_size,
                        price=exit_price, pnl=pnl, reason_for_exit=action.reason
                    )
            except Exception:
                logger.exception(f"Exception closing position for {position.symbol}.")

    def execute_roll_order_actions(self, actions: List[RollOrderAction]):
        if self.config.general.dry_run:
            logger.warning(f"[DRY RUN] Would have rolled {len(actions)} position(s).")
            for action in actions: logger.info(f"[DRY RUN] Roll: Close {action.position_to_close.symbol}, Open {action.new_order_to_open.symbol}")
            return

        for action in actions:
            # 1. Close the old position
            position_to_close = action.position_to_close
            close_side = "buy" if position_to_close.size < 0 else "sell"
            close_size = abs(position_to_close.size)
            close_client_oid = f"dwb_roll_close_{position_to_close.symbol}_{int(time.time() * 1000)}"
            try:
                close_result = self.client.place_order(
                    product_id=position_to_close.instrument_id, size=int(close_size),
                    side=close_side, order_type="market", client_order_id=close_client_oid
                )
                if not close_result:
                    logger.error(f"Failed to place closing order for roll of {position_to_close.symbol}. Aborting roll.")
                    continue

                exit_price = float(close_result.get('avg_fill_price', 0.0))
                pnl = (position_to_close.entry_price - exit_price) * close_size
                self.journal.record_trade(
                    symbol=position_to_close.symbol, side=close_side, size=close_size,
                    price=exit_price, pnl=pnl, reason_for_exit=f"roll_{action.reason}"
                )
            except Exception:
                logger.exception(f"Exception during closing part of roll for {position_to_close.symbol}. Aborting roll.")
                continue

            # 2. Open the new position
            new_order_action = action.new_order_to_open
            self.execute_place_order_actions([new_order_action]) # Reuse the place order logic
