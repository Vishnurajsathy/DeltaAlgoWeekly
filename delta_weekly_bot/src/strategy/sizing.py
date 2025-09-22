from loguru import logger

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot

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
