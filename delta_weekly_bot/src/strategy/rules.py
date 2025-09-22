from loguru import logger
from typing import List, Optional

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot, Position, Option
from ..data.stores import TradeJournal

class PrecheckRules:
    """
    Encapsulates the set of rules to be checked in the PRECHECK state
    before the bot attempts to enter any trades.
    """
    def __init__(self, config: Config, snapshot: MarketDataSnapshot, journal: TradeJournal):
        self.config = config
        self.snapshot = snapshot
        self.journal = journal
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
        Checks if the bot has breached its daily or weekly loss limits by querying the trade journal.
        """
        if not self.snapshot.account_info or self.snapshot.account_info.equity == 0:
            self.errors.append("Loss Limit Check Failed: Cannot check limits without account equity.")
            return False  # Fail safe

        equity = self.snapshot.account_info.equity

        # Check daily loss
        daily_pnl = self.journal.get_daily_pnl()
        if daily_pnl < 0:
            daily_loss_pct = abs(daily_pnl / equity) * 100
            max_daily_loss_pct = self.config.risk.max_daily_loss_pct
            if daily_loss_pct > max_daily_loss_pct:
                self.errors.append(
                    f"Daily Loss Limit BREACHED: Loss of {daily_loss_pct:.2f}% "
                    f"exceeds limit of {max_daily_loss_pct}%."
                )
                return False

        # Check weekly loss
        weekly_pnl = self.journal.get_weekly_pnl()
        if weekly_pnl < 0:
            weekly_loss_pct = abs(weekly_pnl / equity) * 100
            max_weekly_loss_pct = self.config.risk.max_weekly_loss_pct
            if weekly_loss_pct > max_weekly_loss_pct:
                self.errors.append(
                    f"Weekly Loss Limit BREACHED: Loss of {weekly_loss_pct:.2f}% "
                    f"exceeds limit of {max_weekly_loss_pct}%."
                )
                return False

        logger.debug(f"Loss Limit Check: OK (Daily PnL: {daily_pnl:.2f}, Weekly PnL: {weekly_pnl:.2f})")
        return True

    def check_iv_rank(self) -> bool:
        """
        Placeholder for checking if the Implied Volatility Rank (IVR) meets the minimum threshold.
        This requires historical IV data and the analytics module.
        """
        logger.debug("IV Rank Check: SKIPPED (Not Implemented)")
        return True

    def are_all_checks_ok(self) -> bool:
        """
        Runs all pre-check rules and returns True if all pass.
        """
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

class MonitorRules:
    """
    Encapsulates the set of rules to be checked in the MONITOR state
    for a single open position.
    """
    def __init__(self, config: Config, position: Position, spot_price: float, option_details: Optional[Option] = None):
        self.config = config
        self.position = position
        self.spot_price = spot_price
        self.option_details = option_details

    def should_stop_loss(self) -> bool:
        """
        Checks if the position has hit its stop-loss based on the premium received.
        """
        if self.position.size >= 0:
            return False

        stop_loss_pct = self.config.risk.leg_stop_loss_pct
        entry_price = self.position.entry_price
        mark_price = self.position.mark_price

        if entry_price <= 0:
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
        """
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

    def is_leg_threatened(self) -> bool:
        """
        Checks if a short option leg is 'threatened' by the spot price
        moving too close to its strike price.
        """
        if self.position.size >= 0 or not self.option_details:
            return False

        threshold_pct = self.config.adjustments.threaten_threshold_pct_from_strike
        strike_price = self.option_details.strike

        if self.option_details.option_type == 'call':
            threat_level = strike_price * (1 - (threshold_pct / 100.0))
            if self.spot_price >= threat_level:
                logger.warning(
                    f"THREAT DETECTED for CALL {self.position.symbol}: "
                    f"Spot ({self.spot_price:.2f}) >= Threat Level ({threat_level:.2f})"
                )
                return True
        elif self.option_details.option_type == 'put':
            threat_level = strike_price * (1 + (threshold_pct / 100.0))
            if self.spot_price <= threat_level:
                logger.warning(
                    f"THREAT DETECTED for PUT {self.position.symbol}: "
                    f"Spot ({self.spot_price:.2f}) <= Threat Level ({threat_level:.2f})"
                )
                return True

        return False
