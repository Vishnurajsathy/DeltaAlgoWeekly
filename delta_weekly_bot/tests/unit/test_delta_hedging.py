import pytest
from unittest.mock import MagicMock
import copy
from pathlib import Path

from delta_weekly_bot.src.utils.cfg import Config, load_config
from delta_weekly_bot.src.data.models import Position, Ticker, AccountInfo, MarketDataSnapshot
from delta_weekly_bot.src.analytics.greeks import calculate_portfolio_delta
from delta_weekly_bot.src.strategy.sizing import get_delta_hedge_size
from delta_weekly_bot.src.strategy.rules import PortfolioRules

# Load the default config to use in tests
@pytest.fixture(scope="module")
def default_config() -> Config:
    # The load_config function expects the directory, not the file itself
    config_dir = Path("delta_weekly_bot/config")
    return load_config(config_dir)

# --- Tests for calculate_portfolio_delta ---

def test_calculate_portfolio_delta_no_positions():
    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.positions = []
    assert calculate_portfolio_delta(snapshot) == 0.0

def test_calculate_portfolio_delta_with_options_and_futures():
    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.positions = [
        Position(instrument_id=1, symbol="BTC-C", size=2.0, delta=0.5, side="buy", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0),
        Position(instrument_id=2, symbol="BTC-P", size=-3.0, delta=-0.4, side="sell", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0),
        Position(instrument_id=3, symbol="BTC-PERP", size=-0.1, delta=1.0, side="sell", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0),
    ]
    # Expected delta = (2.0 * 0.5) + (-3.0 * -0.4) + (-0.1 * 1.0)
    #                = 1.0 + 1.2 - 0.1 = 2.1
    assert calculate_portfolio_delta(snapshot) == pytest.approx(2.1)

def test_calculate_portfolio_delta_only_futures():
    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.positions = [
        Position(instrument_id=1, symbol="BTC-PERP", size=0.5, delta=1.0, side="buy", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0),
    ]
    assert calculate_portfolio_delta(snapshot) == pytest.approx(0.5)

def test_calculate_portfolio_delta_only_options():
    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.positions = [
        Position(instrument_id=1, symbol="BTC-C", size=-1.0, delta=0.6, side="sell", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0),
        Position(instrument_id=2, symbol="BTC-P", size=-1.0, delta=-0.4, side="sell", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0),
    ]
    # Expected delta = (-1.0 * 0.6) + (-1.0 * -0.4) = -0.6 + 0.4 = -0.2
    assert calculate_portfolio_delta(snapshot) == pytest.approx(-0.2)

# --- Tests for PortfolioRules ---

def test_portfolio_rules_hedge_not_needed(default_config):
    config = copy.deepcopy(default_config)
    config.hedge.delta_hedge_futures.rebalance_threshold = 0.10

    # Portfolio delta is within the threshold
    rules = PortfolioRules(config, portfolio_delta=0.05)
    assert not rules.is_delta_hedge_needed()

    rules = PortfolioRules(config, portfolio_delta=-0.09)
    assert not rules.is_delta_hedge_needed()

def test_portfolio_rules_hedge_is_needed(default_config):
    config = copy.deepcopy(default_config)
    config.hedge.delta_hedge_futures.rebalance_threshold = 0.10

    # Portfolio delta is outside the threshold
    rules = PortfolioRules(config, portfolio_delta=0.11)
    assert rules.is_delta_hedge_needed()

    rules = PortfolioRules(config, portfolio_delta=-0.15)
    assert rules.is_delta_hedge_needed()

    # Portfolio delta is exactly at the threshold (should not trigger)
    rules = PortfolioRules(config, portfolio_delta=0.10)
    assert not rules.is_delta_hedge_needed()

def test_portfolio_rules_hedge_disabled(default_config):
    config = copy.deepcopy(default_config)
    config.hedge.delta_hedge_futures.enabled = False

    # Hedge is disabled, should always be false even if delta is high
    rules = PortfolioRules(config, portfolio_delta=0.5)
    assert not rules.is_delta_hedge_needed()

# --- Tests for get_delta_hedge_size ---

@pytest.fixture
def mock_ticker() -> Ticker:
    # The function under test only uses mark_price, but we need to provide
    # all required fields for Pydantic validation.
    return Ticker(
        product_id=1,
        symbol="BTCUSDT_PERP",
        mark_price=50000.0,
        spot_price=50000.0,
        open=50000,
        close=50000,
        high=50000,
        low=50000,
        volume=1000,
        turnover=50000000,
        oi=100
    )

@pytest.fixture
def mock_account_info() -> AccountInfo:
    # The function under test only uses equity, but we need to provide
    # all required fields for Pydantic validation.
    return AccountInfo(
        username="test_user",
        equity=10000.0,
        balance=10000.0,
        free_collateral=10000.0,
        margin_balance=10000.0,
        initial_margin=0.0,
        maintenance_margin=0.0,
    )

def test_get_delta_hedge_size_basic_no_cap(default_config, mock_ticker, mock_account_info):
    config = copy.deepcopy(default_config)
    # Set a very high cap to test the basic calculation
    config.hedge.delta_hedge_futures.max_futures_notional_vs_equity = 5.0 # 500% of equity

    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.positions = []
    snapshot.futures_ticker = mock_ticker
    snapshot.account_info = mock_account_info

    # We are long 0.2 delta, so we need to sell 0.2 BTC worth of futures
    size = get_delta_hedge_size(portfolio_delta=0.2, snapshot=snapshot, config=config)
    assert size == pytest.approx(-0.2)

    # We are short 0.3 delta, so we need to buy 0.3 BTC worth of futures
    size = get_delta_hedge_size(portfolio_delta=-0.3, snapshot=snapshot, config=config)
    assert size == pytest.approx(0.3)

def test_get_delta_hedge_size_respects_max_notional_from_zero(default_config, mock_ticker, mock_account_info):
    config = copy.deepcopy(default_config)
    # Max futures notional is 0.1 * 10000 equity = $1000
    # At $50k/BTC, this is a max position of 1000 / 50000 = 0.02 BTC
    config.hedge.delta_hedge_futures.max_futures_notional_vs_equity = 0.1

    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.positions = [] # Start with no futures position
    snapshot.futures_ticker = mock_ticker
    snapshot.account_info = mock_account_info

    # We are short 0.8 delta, need to buy 0.8. Capped at 0.02.
    size = get_delta_hedge_size(portfolio_delta=-0.8, snapshot=snapshot, config=config)
    assert size == pytest.approx(0.02)

    # We are long 0.8 delta, need to sell 0.8. Capped at -0.02.
    size = get_delta_hedge_size(portfolio_delta=0.8, snapshot=snapshot, config=config)
    assert size == pytest.approx(-0.02)

def test_get_delta_hedge_size_respects_max_notional_with_existing_pos(default_config, mock_ticker, mock_account_info):
    config = copy.deepcopy(default_config)
    # Max futures notional is 0.2 * 10000 equity = $2000 -> 0.04 BTC
    config.hedge.delta_hedge_futures.max_futures_notional_vs_equity = 0.2

    snapshot = MagicMock(spec=MarketDataSnapshot)
    snapshot.futures_ticker = mock_ticker
    snapshot.account_info = mock_account_info

    # Existing position: long 0.03 BTC. Max is 0.04. Room to add 0.01.
    snapshot.positions = [Position(instrument_id=1, symbol=config.general.symbols.futures, size=0.03, side="buy", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0, delta=1.0)]

    # We are short 0.5 delta. Need to buy 0.5. Capped at adding 0.01.
    size = get_delta_hedge_size(portfolio_delta=-0.5, snapshot=snapshot, config=config)
    assert size == pytest.approx(0.01)

    # Existing position: short 0.03 BTC. Max is -0.04. Room to short 0.01 more.
    snapshot.positions = [Position(instrument_id=1, symbol=config.general.symbols.futures, size=-0.03, side="sell", entry_price=1, mark_price=1, unrealized_pnl=0, realized_pnl=0, delta=1.0)]

    # We are long 0.5 delta. Need to sell 0.5. Capped at selling 0.01 more.
    size = get_delta_hedge_size(portfolio_delta=0.5, snapshot=snapshot, config=config)
    assert size == pytest.approx(-0.01)

    # We are long 0.02 delta (net of options). Need to sell 0.02.
    # We are short 0.03 already. Target is -0.05, but max is -0.04.
    # So we need to sell 0.01 to get to the -0.04 cap.
    size = get_delta_hedge_size(portfolio_delta=0.02, snapshot=snapshot, config=config)
    assert size == pytest.approx(-0.01)
