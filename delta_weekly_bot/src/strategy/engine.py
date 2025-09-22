from typing import List

from loguru import logger

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot
from ..analytics.strikes import select_short_strangle_legs
from ..broker.orders import PlaceOrderAction, CloseOrderAction
from .sizing import get_position_size
from .rules import MonitorRules

class StrategyEngine:
    """
    The core decision-making engine for the trading strategy.
    It processes market data and determines what actions to take based on the current state.
    """
    def __init__(self, config: Config):
        self.config = config
        logger.info("StrategyEngine initialized.")

    def handle_enter_state(self, snapshot: MarketDataSnapshot) -> List[PlaceOrderAction]:
        """
        Handles the logic for the ENTER state. It selects strikes and prepares orders.

        Returns:
            A list of PlaceOrderAction objects if a trade is to be made, otherwise an empty list.
        """
        logger.info("Handling ENTER state: Looking for a new strangle to sell.")

        actions: List[PlaceOrderAction] = []

        # 1. Select the strangle legs from the options chain
        call_leg, put_leg = select_short_strangle_legs(snapshot.options_chain, self.config)

        if not call_leg or not put_leg:
            logger.warning("Could not find a suitable strangle pair. No action will be taken.")
            return actions

        # 2. Determine position size
        size = get_position_size(self.config, snapshot)
        if size <= 0:
            logger.warning(f"Position sizing returned non-positive size: {size}. No action will be taken.")
            return actions

        # 3. Create PlaceOrder actions for each leg
        # For a short strangle, we SELL both the call and the put.

        # Prepare the call leg order
        call_order = PlaceOrderAction(
            product_id=call_leg.instrument_id,
            symbol=call_leg.symbol,
            side="sell",
            size=size,
            order_type="limit",
            limit_price=call_leg.best_bid  # Place order at the best bid to increase chance of getting filled
        )
        actions.append(call_order)
        logger.info(f"Prepared SELL order for call leg: {call_order}")

        # Prepare the put leg order
        put_order = PlaceOrderAction(
            product_id=put_leg.instrument_id,
            symbol=put_leg.symbol,
            side="sell",
            size=size,
            order_type="limit",
            limit_price=put_leg.best_bid
        )
        actions.append(put_order)
        logger.info(f"Prepared SELL order for put leg: {put_order}")

        return actions

    def handle_monitor_state(self, snapshot: MarketDataSnapshot) -> List[CloseOrderAction]:
        """
        Handles the logic for the MONITOR state. It checks each open position
        for stop-loss or take-profit triggers.

        Returns:
            A list of CloseOrderAction objects for any positions that should be closed.
        """
        logger.info(f"Handling MONITOR state: Checking {len(snapshot.positions)} open position(s).")

        actions: List[CloseOrderAction] = []

        if not snapshot.positions:
            return actions

        for position in snapshot.positions:
            rules = MonitorRules(self.config, position)

            should_close = False
            reason = ""

            if rules.should_stop_loss():
                should_close = True
                reason = "stop_loss"

            elif rules.should_take_profit():
                should_close = True
                reason = "take_profit"

            if should_close:
                logger.info(f"Generating close order for {position.symbol} due to: {reason}")
                close_action = CloseOrderAction(
                    position_to_close=position,
                    reason=reason
                )
                actions.append(close_action)

        return actions
