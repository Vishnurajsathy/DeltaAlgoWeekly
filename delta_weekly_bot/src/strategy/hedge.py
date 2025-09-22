from typing import Optional, Tuple

from loguru import logger

from ..data.models import OptionsChain, Option
from ..utils.cfg import Config

def select_monthly_hedge_legs(
    spot_price: float,
    monthly_chain: OptionsChain,
    config: Config
) -> Tuple[Optional[Option], Optional[Option]]:
    """
    Selects the At-The-Money (ATM) call and put for the monthly hedge.

    The ATM strike is the available strike price that is closest to the current
    underlying spot price.
    """
    if not monthly_chain or not monthly_chain.calls:
        logger.warning("Cannot select monthly hedge, the provided options chain is empty.")
        return None, None

    # Find the ATM strike by finding the minimum absolute distance to the spot price
    min_dist = float('inf')
    atm_strike = None

    # We only need to iterate through one side of the chain (e.g., calls) to find the strike
    for call_option in monthly_chain.calls:
        dist = abs(call_option.strike - spot_price)
        if dist < min_dist:
            min_dist = dist
            atm_strike = call_option.strike

    if atm_strike is None:
        logger.error("Could not determine ATM strike from the monthly options chain.")
        return None, None

    logger.info(f"Determined ATM strike for monthly hedge: {atm_strike} (Spot: {spot_price:.2f})")

    # Find the ATM call and put options that correspond to the selected strike
    atm_call = next((opt for opt in monthly_chain.calls if opt.strike == atm_strike), None)
    atm_put = next((opt for opt in monthly_chain.puts if opt.strike == atm_strike), None)

    if not atm_call or not atm_put:
        logger.error(f"Could not find a matching call/put pair for ATM strike {atm_strike}. Chain may be inconsistent.")
        return None, None

    logger.success(f"Selected monthly hedge legs: {atm_call.symbol} and {atm_put.symbol}")

    return atm_call, atm_put
