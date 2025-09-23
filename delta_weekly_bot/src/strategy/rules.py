from loguru import logger
from typing import List, Optional

from ..utils.cfg import Config
from ..data.models import MarketDataSnapshot, Position, Option
from ..data.stores import TradeJournal
from ..data.delta_api import DeltaAPIClient
from datetime import datetime, timedelta, UTC

class PrecheckRules:
    """
    Encapsulates the set of rules to be checked in the PRECHECK state
    before the bot attempts to enter any trades.
    """
    def __init__(self, config: Config, snapshot: MarketDataSnapshot, journal: TradeJournal, client: DeltaAPIClient):
        self.config = config
        self.snapshot = snapshot
        self.journal = journal
        self.client = client
        self.errors: List[str] = []

    def check_api_health(self) -> bool:
        if self.snapshot.account_info is None:
            self.errors.append("API Health Check Failed: Could not retrieve account information.")
            return False
        logger.debug("API Health Check: OK")
        return True

    def check_margin_usage(self) -> bool:
        if not self.snapshot.account_info or self.snapshot.account_info.equity == 0:
            self.errors.append("Margin Check Failed: Account info missing or equity is zero.")
            return False
        account = self.snapshot.account_info
        margin_usage_pct = (account.initial_margin / account.equity) * 100
        max_usage = self.config.risk.max_margin_usage_pct
        if margin_usage_pct > max_usage:
            self.errors.append(f"Margin Check Failed: Usage ({margin_usage_pct:.2f}%) > Limit ({max_usage}%).")
            return False
        logger.debug(f"Margin Usage Check: OK ({margin_usage_pct:.2f}% <= {max_usage}%)")
        return True

    def check_loss_limits(self) -> bool:
        if not self.snapshot.account_info or self.snapshot.account_info.equity == 0:
            self.errors.append("Loss Limit Check Failed: Cannot check limits without account equity.")
            return False
        equity = self.snapshot.account_info
        daily_pnl = self.journal.get_daily_pnl()
        if daily_pnl < 0:
            daily_loss_pct = abs(daily_pnl / equity) * 100
            if daily_loss_pct > self.config.risk.max_daily_loss_pct:
                self.errors.append(f"Daily Loss Limit BREACHED: {daily_loss_pct:.2f}% > {self.config.risk.max_daily_loss_pct}%.")
                return False
        weekly_pnl = self.journal.get_weekly_pnl()
        if weekly_pnl < 0:
            weekly_loss_pct = abs(weekly_pnl / equity) * 100
            if weekly_loss_pct > self.config.risk.max_weekly_loss_pct:
                self.errors.append(f"Weekly Loss Limit BREACHED: {weekly_loss_pct:.2f}% > {self.config.risk.max_weekly_loss_pct}%.")
                return False
        logger.debug(f"Loss Limit Check: OK (Daily PnL: {daily_pnl:.2f}, Weekly PnL: {weekly_pnl:.2f})")
        return True

    def check_iv_rank(self) -> bool:
        # Placeholder - requires historical data logic
        logger.debug("IV Rank Check: SKIPPED (Not Implemented)")
        return True

    def are_all_checks_ok(self) -> bool:
        checks = [self.check_api_health, self.check_margin_usage, self.check_loss_limits, self.check_iv_rank]
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
    Encapsulates rules for monitoring a single open position.
    """
    def __init__(self, config: Config, position: Position, spot_price: float, option_details: Optional[Option] = None):
        self.config = config
        self.position = position
        self.spot_price = spot_price
        self.option_details = option_details

    def should_stop_loss(self) -> bool:
        if self.position.size >= 0 or self.position.entry_price <= 0: return False
        stop_price_threshold = self.position.entry_price * (1 + (self.config.risk.leg_stop_loss_pct / 100.0))
        if self.position.mark_price >= stop_price_threshold:
            logger.warning(f"STOP-LOSS for {self.position.symbol}: Mark ({self.position.mark_price:.2f}) >= Stop ({stop_price_threshold:.2f})")
            return True
        return False

    def should_take_profit(self) -> bool:
        if self.position.size >= 0 or self.position.entry_price <= 0: return False
        profit_price_threshold = self.position.entry_price * (1 - (self.config.risk.take_profit_pct / 100.0))
        if self.position.mark_price <= profit_price_threshold:
            logger.info(f"TAKE-PROFIT for {self.position.symbol}: Mark ({self.position.mark_price:.2f}) <= Target ({profit_price_threshold:.2f})")
            return True
        return False

    def is_leg_threatened(self) -> bool:
        if self.position.size >= 0 or not self.option_details: return False
        threshold_pct = self.config.adjustments.threaten_threshold_pct_from_strike
        strike_price = self.option_details.strike
        if self.option_details.option_type == 'call':
            threat_level = strike_price * (1 - (threshold_pct / 100.0))
            if self.spot_price >= threat_level:
                logger.warning(f"THREAT for CALL {self.position.symbol}: Spot ({self.spot_price:.2f}) >= Level ({threat_level:.2f})")
                return True
        elif self.option_details.option_type == 'put':
            threat_level = strike_price * (1 + (threshold_pct / 100.0))
            if self.spot_price <= threat_level:
                logger.warning(f"THREAT for PUT {self.position.symbol}: Spot ({self.spot_price:.2f}) <= Level ({threat_level:.2f})")
                return True
        return False

class PortfolioRules:
    """
    Encapsulates rules that apply to the portfolio as a whole.
    """
    def __init__(self, config: Config, portfolio_delta: float):
        self.config = config
        self.portfolio_delta = portfolio_delta

    def is_delta_hedge_needed(self) -> bool:
        if not self.config.hedge.delta_hedge_futures.enabled: return False
        threshold = self.config.hedge.delta_hedge_futures.rebalance_threshold
        if abs(self.portfolio_delta) > threshold:
            logger.warning(f"DELTA HEDGE TRIGGERED: |{self.portfolio_delta:.4f}| > {threshold:.4f}")
            return True
        logger.debug(f"Delta Hedge Check: OK (|{self.portfolio_delta:.4f}| <= {threshold:.4f})")
        return False
