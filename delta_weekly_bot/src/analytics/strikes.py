from typing import Optional, Tuple, List

from loguru import logger

from ..data.models import OptionsChain, Option
from ..utils.cfg import Config

def select_short_strangle_legs(chain: OptionsChain, config: Config) -> Tuple[Optional[Option], Optional[Option]]:
    """
    Selects the best call and put options to sell for a short strangle strategy.
    """
    if not chain or not (chain.calls and chain.puts):
        logger.warning("Cannot select strikes, options chain is empty or invalid.")
        return None, None

    target_delta_min = config.entry.weekly_target_delta[0]
    target_delta_max = config.entry.weekly_target_delta[1]
    min_credit = config.entry.min_credit_usdt_per_leg

    # --- Select Call Leg ---
    eligible_calls = [
        opt for opt in chain.calls
        if opt.greeks and target_delta_min <= opt.greeks.delta <= target_delta_max
    ]
    eligible_calls.sort(key=lambda o: o.strike, reverse=True)

    selected_call: Optional[Option] = None
    for call in eligible_calls:
        if call.best_bid >= min_credit:
            selected_call = call
            logger.info(
                f"Selected Call Leg: {call.symbol} (Strike: {call.strike}, "
                f"Delta: {call.greeks.delta:.2f}, Credit: {call.best_bid})"
            )
            break

    if not selected_call and eligible_calls:
        logger.warning(f"Found {len(eligible_calls)} calls in delta range, but none met minimum credit.")

    # --- Select Put Leg ---
    eligible_puts = [
        opt for opt in chain.puts
        if opt.greeks and target_delta_min <= abs(opt.greeks.delta) <= target_delta_max
    ]
    eligible_puts.sort(key=lambda o: o.strike)

    selected_put: Optional[Option] = None
    for put in eligible_puts:
        if put.best_bid >= min_credit:
            selected_put = put
            logger.info(
                f"Selected Put Leg: {put.symbol} (Strike: {put.strike}, "
                f"Delta: {put.greeks.delta:.2f}, Credit: {put.best_bid})"
            )
            break

    if not selected_put and eligible_puts:
        logger.warning(f"Found {len(eligible_puts)} puts in delta range, but none met minimum credit.")

    if not selected_call or not selected_put:
        logger.warning("Could not find a complete strangle pair.")

    return selected_call, selected_put

def select_new_leg_for_roll(
    threatened_leg: Option,
    chain: OptionsChain,
    config: Config
) -> Optional[Option]:
    """
    Selects a new option to roll a threatened leg to.
    """
    logger.info(f"Searching for a new leg to roll the threatened position: {threatened_leg.symbol}")

    target_delta_min = config.entry.weekly_target_delta[0]
    target_delta_max = config.entry.weekly_target_delta[1]
    min_credit = config.entry.min_credit_usdt_per_leg

    eligible_rolls: List[Option] = []

    if threatened_leg.option_type == 'call':
        candidate_rolls = [opt for opt in chain.calls if opt.strike > threatened_leg.strike]
        eligible_rolls = [
            opt for opt in candidate_rolls
            if opt.greeks and target_delta_min <= opt.greeks.delta <= target_delta_max and opt.best_bid >= min_credit
        ]
        eligible_rolls.sort(key=lambda o: o.strike)

    elif threatened_leg.option_type == 'put':
        candidate_rolls = [opt for opt in chain.puts if opt.strike < threatened_leg.strike]
        eligible_rolls = [
            opt for opt in candidate_rolls
            if opt.greeks and target_delta_min <= abs(opt.greeks.delta) <= target_delta_max and opt.best_bid >= min_credit
        ]
        eligible_rolls.sort(key=lambda o: o.strike, reverse=True)

    if not eligible_rolls:
        logger.warning(f"No suitable roll found for threatened {threatened_leg.option_type} leg {threatened_leg.symbol}")
        return None

    best_roll = eligible_rolls[0]
    logger.success(f"Found best roll for {threatened_leg.symbol}: {best_roll.symbol} at strike {best_roll.strike}")
    return best_roll
