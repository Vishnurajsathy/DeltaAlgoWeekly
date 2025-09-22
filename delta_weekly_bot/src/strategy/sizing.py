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
