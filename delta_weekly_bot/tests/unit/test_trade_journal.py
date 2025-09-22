import unittest
import sqlite3
from datetime import datetime, timedelta, UTC

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.stores import TradeJournal

class TestTradeJournal(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        # Using ":memory:" makes the database transient and perfect for testing.
        self.journal = TradeJournal(":memory:")

    def tearDown(self):
        """Close the database connection after each test."""
        self.journal.close()

    def test_record_trade(self):
        """Test that a trade is correctly inserted into the database."""
        self.journal.record_trade(
            symbol="BTC-25OCT24-50000-C",
            side="sell",
            size=1.0,
            price=100.0,
            pnl=None,
            reason_for_exit=None
        )

        # Query the DB directly to verify the row was inserted correctly
        cursor = self.journal.conn.cursor()
        cursor.execute("SELECT * FROM trades")
        row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row['symbol'], "BTC-25OCT24-50000-C")
        self.assertEqual(row['side'], "sell")
        self.assertEqual(row['size'], 1.0)
        self.assertEqual(row['price'], 100.0)
        self.assertIsNone(row['pnl'])

    def test_get_daily_pnl(self):
        """Test the daily P&L calculation."""
        # Record some trades with P&L for today
        self.journal.record_trade("SYM1", "buy", 1, 100, pnl=50.0)
        self.journal.record_trade("SYM2", "buy", 1, 100, pnl=-20.0) # A loss

        # Manually insert a trade from yesterday to ensure it's ignored by the daily query
        yesterday = datetime.now(UTC) - timedelta(days=1)
        cursor = self.journal.conn.cursor()
        cursor.execute("INSERT INTO trades (timestamp, symbol, side, size, price, pnl) VALUES (?, ?, ?, ?, ?, ?)",
                       (yesterday, "SYM3", "buy", 1, 100, 1000.0))
        self.journal.conn.commit()

        daily_pnl = self.journal.get_daily_pnl()
        self.assertAlmostEqual(daily_pnl, 30.0)

    def test_get_weekly_pnl(self):
        """Test the weekly P&L calculation."""
        self.journal.record_trade("SYM1", "buy", 1, 100, pnl=100.0)

        # Manually insert a trade from 6 days ago (should be included)
        six_days_ago = datetime.now(UTC) - timedelta(days=6)
        cursor = self.journal.conn.cursor()
        cursor.execute("INSERT INTO trades (timestamp, symbol, side, size, price, pnl) VALUES (?, ?, ?, ?, ?, ?)",
                       (six_days_ago, "SYM2", "buy", 1, 100, 50.0))

        # Manually insert a trade from 8 days ago (should be ignored)
        eight_days_ago = datetime.now(UTC) - timedelta(days=8)
        cursor.execute("INSERT INTO trades (timestamp, symbol, side, size, price, pnl) VALUES (?, ?, ?, ?, ?, ?)",
                       (eight_days_ago, "SYM3", "buy", 1, 100, 1000.0))
        self.journal.conn.commit()

        weekly_pnl = self.journal.get_weekly_pnl()
        self.assertAlmostEqual(weekly_pnl, 150.0)

    def test_pnl_is_zero_when_no_trades_with_pnl(self):
        """Test that PNL is zero when there are no trades with PNL recorded."""
        self.journal.record_trade("SYM1", "sell", 1, 100) # Entry trade, no PNL
        daily_pnl = self.journal.get_daily_pnl()
        self.assertEqual(daily_pnl, 0.0)
        weekly_pnl = self.journal.get_weekly_pnl()
        self.assertEqual(weekly_pnl, 0.0)

if __name__ == '__main__':
    unittest.main()
