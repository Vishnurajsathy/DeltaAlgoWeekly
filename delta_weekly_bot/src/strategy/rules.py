from loguru import logger
from typing import List

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot

class PrecheckRules:
    """
    Encapsulates the set of rules to be checked in the PRECHECK state
    before the bot attempts to enter any trades.
    """
    def __init__(self, config: Config, snapshot: MarketDataSnapshot):
        self.config = config
        self.snapshot = snapshot
        self.errors: List[str] = []

    def check_api_health(self) -> bool:
        """
        Checks if the API is responsive and we have the necessary data.
        A simple check is to ensure we have account information.
        """
        if self.snapshot.account_info is None:
            self.errors.append("API Health Check Failed: Could not retrieve account information.")
            return False
        logger.debug("API Health Check: OK")
        return True

    def check_margin_usage(self) -> bool:
        """
        Checks if the current margin usage is within the configured limit.
        """
        if not self.snapshot.account_info or self.snapshot.account_info.equity == 0:
            self.errors.append("Margin Check Failed: Account info missing or equity is zero.")
            return False

        account = self.snapshot.account_info
        margin_usage_pct = (account.initial_margin / account.equity) * 100
        max_usage = self.config.risk.max_margin_usage_pct

        if margin_usage_pct > max_usage:
            self.errors.append(
                f"Margin Check Failed: Current usage ({margin_usage_pct:.2f}%) exceeds max limit ({max_usage}%)."
            )
            return False

        logger.debug(f"Margin Usage Check: OK ({margin_usage_pct:.2f}% <= {max_usage}%)")
        return True

    def check_loss_limits(self) -> bool:
        """
        Placeholder for checking daily/weekly loss limits.
        This requires a persistent trade journal, which is not yet implemented.
        """
        # TODO: Implement this once the trade journal (e.g., SQLite) is available.
        # This will involve querying the journal for recent P&L and comparing against
        # config.risk.max_daily_loss_pct and config.risk.max_weekly_loss_pct.
        logger.debug("Loss Limit Check: SKIPPED (Not Implemented)")
        return True

    def check_iv_rank(self) -> bool:
        """
        Placeholder for checking if the Implied Volatility Rank (IVR) meets the minimum threshold.
        This requires historical IV data and the analytics module.
        """
        # TODO: Implement this once the analytics/iv.py module is built.
        # This will involve fetching historical IV, calculating IVR, and comparing against
        # config.filters.iv.min_ivr.
        logger.debug("IV Rank Check: SKIPPED (Not Implemented)")
        return True

    def are_all_checks_ok(self) -> bool:
        """
        Runs all pre-check rules and returns True if all pass.
        Logs any failures.
        """
        # The order matters, check API health first.
        checks = [
            self.check_api_health,
            self.check_margin_usage,
            self.check_loss_limits,
            self.check_iv_rank,
        ]

        all_ok = all(check() for check in checks)

        if not all_ok:
            logger.warning("PRECHECK failed. Reasons:")
            for error in self.errors:
                logger.warning(f"- {error}")
        else:
            logger.info("All PRECHECK rules passed successfully.")

        return all_ok

from ..data.models import Position

class MonitorRules:
    """
    Encapsulates the set of rules to be checked in the MONITOR state
    for a single open position.
    """
    def __init__(self, config: Config, position: Position):
        self.config = config
        self.position = position

    def should_stop_loss(self) -> bool:
        """
        Checks if the position has hit its stop-loss based on the premium received.
        For a short position, this triggers if the mark price rises significantly.
        Stop Loss = Entry Price * (1 + SL%)
        """
        # This rule only applies to short positions (negative size)
        if self.position.size >= 0:
            return False

        stop_loss_pct = self.config.risk.leg_stop_loss_pct
        entry_price = self.position.entry_price
        mark_price = self.position.mark_price

        if entry_price <= 0:  # Cannot calculate percentage-based SL on zero or negative credit
            return False

        stop_price_threshold = entry_price * (1 + (stop_loss_pct / 100.0))

        if mark_price >= stop_price_threshold:
            logger.warning(
                f"STOP-LOSS TRIGGERED for {self.position.symbol}: "
                f"Mark Price ({mark_price:.2f}) >= Stop Threshold ({stop_price_threshold:.2f})"
            )
            return True

        return False

    def should_take_profit(self) -> bool:
        """
        Checks if the position has reached its take-profit target based on premium decay.
        For a short position, this triggers if the mark price falls significantly.
        Take Profit Price = Entry Price * (1 - TP%)
        """
        # This rule only applies to short positions
        if self.position.size >= 0:
            return False

        take_profit_pct = self.config.risk.take_profit_pct
        entry_price = self.position.entry_price
        mark_price = self.position.mark_price

        if entry_price <= 0:
            return False

        profit_price_threshold = entry_price * (1 - (take_profit_pct / 100.0))

        if mark_price <= profit_price_threshold:
            logger.info(
                f"TAKE-PROFIT TRIGGERED for {self.position.symbol}: "
                f"Mark Price ({mark_price:.2f}) <= Profit Threshold ({profit_price_threshold:.2f})"
            )
            return True

        return False
