from loguru import logger

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot, Ticker, AccountInfo

def get_position_size(config: Config, snapshot: MarketDataSnapshot) -> int:
    """
    Calculates the number of contracts to trade for a new position.

    TODO: Implement proper risk-based sizing logic.
    This could be based on a fixed percentage of equity, volatility, etc.
    For now, it returns a hardcoded placeholder size.
    """
    logger.info("Sizing: Using placeholder position size of 1 contract.")
    return 1

def get_hedge_size(short_leg_size: int, config: Config) -> int:
    """
    Calculates the size for the hedge position based on a notional ratio
    to the primary short position size.
    """
    if short_leg_size <= 0:
        return 0

    ratio = config.hedge.notionals_ratio

    # Simplified calculation assumes contract sizes are equal.
    # Notional value is proportional to number of contracts.
    hedge_size_float = short_leg_size * ratio

    # Round to the nearest whole contract, ensuring a minimum of 1 if ratio > 0.
    hedge_size = max(1, round(hedge_size_float)) if ratio > 0 else 0

    logger.info(
        f"Calculated hedge size: {hedge_size} contracts "
        f"(Short leg size: {short_leg_size}, Ratio: {ratio})"
    )

    return hedge_size

def get_delta_hedge_size(
    portfolio_delta: float,
    snapshot: MarketDataSnapshot,
    config: Config
) -> float:
    """
    Calculates the size of the futures hedge needed to neutralize the portfolio delta.
    The size is capped by the max_futures_notional_vs_equity setting, considering
    any existing futures position.
    """
    if not config.hedge.delta_hedge_futures.enabled:
        return 0.0

    if not snapshot.futures_ticker or not snapshot.account_info:
        logger.error("Cannot calculate delta hedge size without futures ticker or account info.")
        return 0.0

    # 1. Find existing futures position size
    existing_futures_size = 0.0
    for pos in snapshot.positions:
        if pos.symbol == config.general.symbols.futures:
            existing_futures_size = pos.size
            break

    # 2. Calculate the desired adjustment size to bring delta to zero
    required_adjustment_size = -portfolio_delta

    # 3. Calculate what the final position and notional would be after the adjustment
    target_futures_size = existing_futures_size + required_adjustment_size
    target_notional = abs(target_futures_size) * snapshot.futures_ticker.mark_price

    # 4. Calculate the maximum allowed notional for the futures hedge
    max_notional = snapshot.account_info.equity * config.hedge.delta_hedge_futures.max_futures_notional_vs_equity

    # 5. Cap the adjustment if the target notional exceeds the max
    final_adjustment_size = required_adjustment_size
    if target_notional > max_notional:
        allowed_total_size = max_notional / snapshot.futures_ticker.mark_price

        # We cap the *total* position size, then figure out the required adjustment
        if target_futures_size > 0:
            capped_target_size = allowed_total_size
        else:
            capped_target_size = -allowed_total_size

        final_adjustment_size = capped_target_size - existing_futures_size

        logger.warning(
            f"Target delta hedge notional ({target_notional:,.2f}) exceeds max limit "
            f"({max_notional:,.2f}). Capping adjustment to {final_adjustment_size:.4f}."
        )

    # TODO: Round to the nearest tradable lot size for the futures contract.
    logger.info(f"Calculated delta hedge adjustment size: {final_adjustment_size:.4f} contracts.")
    return final_adjustment_size
