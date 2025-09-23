import numpy as np
from typing import List

from loguru import logger

def calculate_historical_volatility(closing_prices: List[float], annualization_factor: int = 365) -> float:
    """
    Calculates the annualized historical volatility from a series of closing prices.
    This is typically used as a proxy for IV when historical IV is not available.
    """
    if len(closing_prices) < 2:
        logger.warning("Not enough data points to calculate historical volatility.")
        return 0.0

    # Calculate logarithmic returns
    log_returns = np.log(np.array(closing_prices) / np.roll(np.array(closing_prices), 1))[1:]

    # Calculate the standard deviation of log returns
    daily_std_dev = np.std(log_returns)

    # Annualize the standard deviation
    historical_volatility = daily_std_dev * np.sqrt(annualization_factor)

    logger.debug(f"Calculated annualized historical volatility: {historical_volatility:.2%}")
    return historical_volatility

def calculate_iv_rank(current_iv: float, historical_iv_series: List[float]) -> float:
    """
    Calculates the Implied Volatility Rank (IVR).
    IVR = (Current IV - Period Low IV) / (Period High IV - Period Low IV)
    Returns a value as a percentage (0-100).
    """
    if not historical_iv_series:
        logger.warning("Historical IV series is empty. Cannot calculate IV Rank.")
        return -1.0  # Return a sentinel value indicating an error

    min_iv = min(historical_iv_series)
    max_iv = max(historical_iv_series)

    if max_iv == min_iv:
        logger.warning("Max IV equals Min IV. Cannot calculate IV Rank (division by zero). Returning 50.0 as neutral.")
        # If max and min are the same, rank is arguably 0 if current is min, or 100 if current is max.
        # A neutral 50 is a safe default.
        return 50.0

    ivr = ((current_iv - min_iv) / (max_iv - min_iv)) * 100

    # Clamp the value between 0 and 100, as current IV could be outside the historical range.
    clamped_ivr = max(0, min(100, ivr))
    logger.debug(f"Calculated IVR: {clamped_ivr:.2f}% (Current: {current_iv}, Range: [{min_iv}, {max_iv}])")

    return clamped_ivr
