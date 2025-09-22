from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Greeks(BaseModel):
    """A model for the greeks of an option."""
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float

class Option(BaseModel):
    """A model for a single options contract."""
    instrument_id: int
    symbol: str
    expiry: datetime
    strike: float
    option_type: str  # "call" or "put"

    # Market data
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    last_price: Optional[float] = None

    # Analytics
    greeks: Optional[Greeks] = None
    open_interest: Optional[float] = None

class OptionsChain(BaseModel):
    """Represents the full options chain for a given expiry."""
    underlying: str
    expiry: datetime
    calls: List[Option]
    puts: List[Option]

class Position(BaseModel):
    """Represents an open position in a single instrument."""
    instrument_id: int
    symbol: str
    size: float
    side: str  # "buy" or "sell"
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    realized_pnl: float

class AccountInfo(BaseModel):
    """Represents overall account information."""
    username: str
    equity: float
    balance: float
    free_collateral: float
    margin_balance: float
    initial_margin: float
    maintenance_margin: float

class Order(BaseModel):
    """Represents a single order (live or historical)."""
    order_id: str
    client_order_id: Optional[str] = None
    instrument_id: int
    price: float
    size: float
    side: str  # "buy" or "sell"
    status: str  # e.g., "open", "filled", "cancelled"
    order_type: str  # e.g., "limit", "market"
    created_at: datetime

class Ticker(BaseModel):
    """Pydantic model for a single ticker response from the API."""
    product_id: int
    symbol: str
    open: float
    close: float
    high: float
    low: float
    volume: int
    turnover: float
    mark_price: float
    spot_price: float
    oi: float
    greeks: Optional[Greeks] = None

class MarketDataSnapshot(BaseModel):
    """
    A snapshot of all market and account data fetched in a single cycle.
    This serves as the main data object passed through the strategy logic.
    """
    timestamp: datetime
    account_info: Optional[AccountInfo] = None
    positions: List[Position] = []
    options_chain: Optional[OptionsChain] = None  # This will be for the weekly options
    monthly_options_chain: Optional[OptionsChain] = None  # For the monthly hedge
    futures_ticker: Optional[Ticker] = None
