from typing import Optional, Tuple

from loguru import logger

from ..data.models import OptionsChain, Option
from ..utils.cfg import Config

def select_short_strangle_legs(chain: OptionsChain, config: Config) -> Tuple[Optional[Option], Optional[Option]]:
    """
    Selects the best call and put options to sell for a short strangle strategy.

    The logic follows these rules:
    1. Find all options with delta within the target range from the config.
    2. Of those, select the one farthest OTM (highest strike for calls, lowest for puts).
    3. Ensure the premium for the selected option meets the minimum credit.
    4. (Placeholder) Ensure the strike is a minimum sigma distance away.

    Returns a tuple of (selected_call, selected_put). Each can be None if no suitable leg is found.
    """
    if not chain or not (chain.calls and chain.puts):
        logger.warning("Cannot select strikes, options chain is empty or invalid.")
        return None, None

    target_delta_min = config.entry.weekly_target_delta[0]
    target_delta_max = config.entry.weekly_target_delta[1]
    min_credit = config.entry.min_credit_usdt_per_leg

    # --- Select Call Leg ---

    # Filter calls by delta range
    eligible_calls = [
        opt for opt in chain.calls
        if opt.greeks and target_delta_min <= opt.greeks.delta <= target_delta_max
    ]

    # Sort by strike price descending to find the farthest OTM
    eligible_calls.sort(key=lambda o: o.strike, reverse=True)

    selected_call: Optional[Option] = None
    for call in eligible_calls:
        # We are selling, so we look at the bid price for the premium we can get.
        if call.best_bid >= min_credit:
            # TODO: Add sigma distance check here once historical volatility is available.
            selected_call = call
            logger.info(
                f"Selected Call Leg: {call.symbol} (Strike: {call.strike}, "
                f"Delta: {call.greeks.delta:.2f}, Credit: {call.best_bid})"
            )
            break  # Found the best one that meets all criteria

    if not selected_call and eligible_calls:
        logger.warning(f"Found {len(eligible_calls)} calls in delta range, but none met the minimum credit of ${min_credit}.")

    # --- Select Put Leg ---

    # Filter puts by delta range (using absolute value for negative put deltas)
    eligible_puts = [
        opt for opt in chain.puts
        if opt.greeks and target_delta_min <= abs(opt.greeks.delta) <= target_delta_max
    ]

    # Sort by strike price ascending to find the farthest OTM
    eligible_puts.sort(key=lambda o: o.strike)

    selected_put: Optional[Option] = None
    for put in eligible_puts:
        if put.best_bid >= min_credit:
            # TODO: Add sigma distance check here.
            selected_put = put
            logger.info(
                f"Selected Put Leg: {put.symbol} (Strike: {put.strike}, "
                f"Delta: {put.greeks.delta:.2f}, Credit: {put.best_bid})"
            )
            break  # Found the best one

    if not selected_put and eligible_puts:
        logger.warning(f"Found {len(eligible_puts)} puts in delta range, but none met the minimum credit of ${min_credit}.")

    if not selected_call or not selected_put:
        logger.warning("Could not find a complete strangle pair. One or both legs are missing.")

    return selected_call, selected_put
