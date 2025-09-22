from typing import List

from loguru import logger

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot
from ..analytics.strikes import select_short_strangle_legs
from typing import Union
from ..broker.orders import PlaceOrderAction, CloseOrderAction, RollOrderAction
from .sizing import get_position_size
from .rules import MonitorRules
from .strikes import select_new_leg_for_roll


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

    def handle_monitor_state(self, snapshot: MarketDataSnapshot) -> List[Union[CloseOrderAction, RollOrderAction]]:
        """
        Handles the logic for the MONITOR state. It checks each open position
        for SL/TP triggers or threats that require adjustment.
        """
        logger.info(f"Handling MONITOR state: Checking {len(snapshot.positions)} open position(s).")

        actions: List[Union[CloseOrderAction, RollOrderAction]] = []

        if not snapshot.positions or not snapshot.options_chain or not snapshot.futures_ticker:
            logger.warning("Cannot monitor positions without position data, options chain, or spot price.")
            return actions

        # Create a quick lookup map for option details by instrument ID for efficient matching
        option_details_map = {opt.instrument_id: opt for opt in snapshot.options_chain.calls}
        option_details_map.update({opt.instrument_id: opt for opt in snapshot.options_chain.puts})

        spot_price = snapshot.futures_ticker.mark_price

        for position in snapshot.positions:
            option_details = option_details_map.get(position.instrument_id)
            if not option_details:
                logger.warning(f"Could not find option details for position {position.symbol}. Skipping monitoring checks.")
                continue

            rules = MonitorRules(self.config, position, spot_price, option_details)

            if rules.should_stop_loss():
                actions.append(CloseOrderAction(position_to_close=position, reason="stop_loss"))
            elif rules.should_take_profit():
                actions.append(CloseOrderAction(position_to_close=position, reason="take_profit"))
            elif rules.is_leg_threatened():
                logger.info(f"Leg {position.symbol} is threatened. Attempting to find a roll opportunity.")
                new_leg_option = select_new_leg_for_roll(option_details, snapshot.options_chain, self.config)

                if new_leg_option:
                    size = abs(position.size)
                    place_order_action = PlaceOrderAction(
                        product_id=new_leg_option.instrument_id,
                        symbol=new_leg_option.symbol,
                        side="sell",
                        size=int(size),
                        order_type="limit",
                        limit_price=new_leg_option.best_bid
                    )
                    roll_action = RollOrderAction(
                        position_to_close=position,
                        new_order_to_open=place_order_action,
                        reason="threatened"
                    )
                    actions.append(roll_action)
                    logger.success(f"Generated roll action for {position.symbol} to {new_leg_option.symbol}.")
                else:
                    logger.warning(f"Leg {position.symbol} is threatened, but no suitable roll opportunity was found. Taking no action.")

        return actions
