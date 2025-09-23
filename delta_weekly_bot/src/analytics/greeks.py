from typing import List, Dict

from loguru import logger

from ..data.models import Position, MarketDataSnapshot, Option

def calculate_portfolio_delta(snapshot: MarketDataSnapshot) -> float:
    """
    Calculates the total delta of all positions in the portfolio by summing
    the delta of each position. For futures, delta is assumed to be 1.
    """
    if not snapshot or not snapshot.positions:
        return 0.0

    total_delta = 0.0
    for p in snapshot.positions:
        # The delta for futures is 1.0, and the API might return null for it.
        # The Position model's delta field is populated by the ingestor.
        # For futures, we can assume the ingestor sets it to 1.0 or it's None.
        position_delta = p.delta if p.delta is not None else 1.0

        # Ensure we have a delta to work with
        if position_delta is None:
             logger.warning(f"Position {p.symbol} has no delta information. Skipping.")
             continue

        total_delta += p.size * position_delta

    logger.info(f"Calculated total portfolio delta: {total_delta:.4f}")
    return total_delta
