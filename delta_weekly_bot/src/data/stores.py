import sqlite3
from datetime import datetime, timedelta, UTC
from pathlib import Path
# --- Custom Adapters for SQLite Datetime Deprecation ---
# https://docs.python.org/3.12/library/sqlite3.html#adapter-and-converter-recipes
def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 format."""
    return val.isoformat()
def convert_timestamp(val):
    """Convert ISO 8601 string from database to a datetime object."""
    return datetime.fromisoformat(val.decode())
sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("timestamp", convert_timestamp)
# --- End Custom Adapters ---
from typing import Optional

from loguru import logger

class TradeJournal:
    """
    Handles persistent storage of trade history using SQLite.
    This provides a reliable way to track performance and enforce cumulative risk limits.
    """
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        # Ensure the directory for the database exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        try:
            # Using detect_types to automatically handle timestamp conversion
            self.conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"TradeJournal connected to database at: {self.db_path}")
            self._create_table()
        except sqlite3.Error as e:
            logger.exception(f"Database connection error: {e}")
            raise

    def _create_table(self):
        """Creates the 'trades' table if it doesn't already exist."""
        try:
            cursor = self.conn.cursor()
            # Storing PNL and reason for exit allows for detailed performance analysis.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL NOT NULL,
                    pnl REAL,
                    reason_for_exit TEXT
                )
            """)
            self.conn.commit()
            logger.info("'trades' table created or already exists.")
        except sqlite3.Error as e:
            logger.exception(f"Failed to create 'trades' table: {e}")

    def record_trade(
        self, symbol: str, side: str, size: float, price: float,
        pnl: Optional[float] = None, reason_for_exit: Optional[str] = None
    ):
        """Records a single trade event into the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trades (timestamp, symbol, side, size, price, pnl, reason_for_exit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now(UTC), symbol, side, size, price, pnl, reason_for_exit))
            self.conn.commit()
            logger.info(f"Recorded trade to journal: {side} {size} {symbol} @ {price}")
        except sqlite3.Error as e:
            logger.exception(f"Failed to record trade for {symbol}: {e}")

    def _get_pnl_since(self, start_time: datetime) -> float:
        """Helper function to get total realized PNL since a given datetime (UTC)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT SUM(pnl) FROM trades
                WHERE timestamp >= ? AND pnl IS NOT NULL
            """, (start_time,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0.0
        except sqlite3.Error as e:
            logger.exception(f"Failed to query PNL since {start_time}: {e}")
            return 0.0

    def get_daily_pnl(self) -> float:
        """Calculates the total realized PNL for the current day (since 00:00 UTC)."""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return self._get_pnl_since(today_start)

    def get_weekly_pnl(self) -> float:
        """Calculates the total realized PNL for the last 7 days."""
        week_ago = datetime.now(UTC) - timedelta(days=7)
        return self._get_pnl_since(week_ago)

    def close(self):
        """Closes the database connection gracefully."""
        if self.conn:
            self.conn.close()
            logger.info("TradeJournal database connection closed.")
