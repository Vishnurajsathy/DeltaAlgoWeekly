from typing import List, Union

from loguru import logger

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot
from ..analytics.strikes import select_short_strangle_legs, select_new_leg_for_roll
from ..broker.orders import PlaceOrderAction, CloseOrderAction, RollOrderAction
from .sizing import get_position_size, get_hedge_size
from .rules import MonitorRules
from .hedge import select_monthly_hedge_legs

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
        Handles the logic for the ENTER state. It selects strikes and prepares orders
        for both the primary strategy and the hedge.
        """
        logger.info("Handling ENTER state: Looking for a new strangle to sell.")

        actions: List[PlaceOrderAction] = []

        # 1. Select the short strangle legs
        call_leg, put_leg = select_short_strangle_legs(snapshot.options_chain, self.config)

        if not call_leg or not put_leg:
            logger.warning("Could not find a suitable strangle pair. No action will be taken.")
            return actions

        # 2. Determine position size for the short legs
        size = get_position_size(self.config, snapshot)
        if size <= 0:
            logger.warning(f"Position sizing returned non-positive size: {size}. No action will be taken.")
            return actions

        # 3. Create PlaceOrder actions for the short strangle
        actions.append(PlaceOrderAction(
            product_id=call_leg.instrument_id, symbol=call_leg.symbol, side="sell",
            size=size, order_type="limit", limit_price=call_leg.best_bid
        ))
        actions.append(PlaceOrderAction(
            product_id=put_leg.instrument_id, symbol=put_leg.symbol, side="sell",
            size=size, order_type="limit", limit_price=put_leg.best_bid
        ))
        logger.info(f"Prepared SELL orders for primary strangle legs.")

        # 4. If hedging is enabled, prepare hedge orders
        if self.config.hedge.type == "monthly_atm_straddle":
            logger.info("Monthly ATM straddle hedge is enabled. Selecting hedge legs.")

            if not snapshot.monthly_options_chain or not snapshot.futures_ticker:
                logger.error("Cannot select hedge, monthly chain or spot price is missing.")
                return actions

            hedge_call, hedge_put = select_monthly_hedge_legs(
                spot_price=snapshot.futures_ticker.mark_price,
                monthly_chain=snapshot.monthly_options_chain,
                config=self.config
            )

            if hedge_call and hedge_put:
                hedge_size = get_hedge_size(short_leg_size=size, config=self.config)
                if hedge_size > 0:
                    actions.append(PlaceOrderAction(
                        product_id=hedge_call.instrument_id, symbol=hedge_call.symbol, side="buy",
                        size=hedge_size, order_type="market"
                    ))
                    actions.append(PlaceOrderAction(
                        product_id=hedge_put.instrument_id, symbol=hedge_put.symbol, side="buy",
                        size=hedge_size, order_type="market"
                    ))
                    logger.info(f"Prepared BUY orders for hedge legs.")
            else:
                logger.error("Could not select monthly hedge legs! Proceeding with unhedged short position.")

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

        option_details_map = {opt.instrument_id: opt for opt in snapshot.options_chain.calls}
        option_details_map.update({opt.instrument_id: opt for opt in snapshot.options_chain.puts})

        spot_price = snapshot.futures_ticker.mark_price

        for position in snapshot.positions:
            option_details = option_details_map.get(position.instrument_id)
            if not option_details:
                logger.warning(f"Could not find option details for position {position.symbol}. Skipping.")
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
                    logger.warning(f"Leg {position.symbol} is threatened, but no suitable roll opportunity was found.")

        return actions
