import unittest
from dataclasses import dataclass

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.strategy.rules import MonitorRules
from src.data.models import Position

# --- Mock Objects for Testing ---

@dataclass
class MockConfig:
    risk: 'MockRiskConfig'

@dataclass
class MockRiskConfig:
    leg_stop_loss_pct: float
    take_profit_pct: float

def create_mock_position(symbol: str, side: str, size: float, entry: float, mark: float) -> Position:
    """Helper function to create mock Position objects."""
    return Position(
        instrument_id=hash(symbol),
        symbol=symbol,
        # Short positions have a negative size in our logic
        size=-size if side == 'sell' else size,
        side=side,
        entry_price=entry,
        mark_price=mark,
        unrealized_pnl=0,
        realized_pnl=0
    )

class TestMonitoringRules(unittest.TestCase):
    """Unit tests for the position monitoring rules (SL/TP)."""

    def setUp(self):
        """Set up a default config object for all tests."""
        self.config = MockConfig(
            risk=MockRiskConfig(
                leg_stop_loss_pct=100.0,  # SL triggers if mark_price >= 2 * entry_price
                take_profit_pct=50.0     # TP triggers if mark_price <= 0.5 * entry_price
            )
        )

    def test_stop_loss_triggered(self):
        """Test when mark price exceeds the stop-loss threshold."""
        # Entry at $10, SL is 100%, so threshold is $20. Mark price is $21.
        position = create_mock_position("P1", "sell", 1, 10.0, 21.0)
        rules = MonitorRules(self.config, position)
        self.assertTrue(rules.should_stop_loss())

    def test_stop_loss_not_triggered(self):
        """Test when mark price is below the stop-loss threshold."""
        # Entry at $10, SL threshold is $20. Mark price is $19.
        position = create_mock_position("P1", "sell", 1, 10.0, 19.0)
        rules = MonitorRules(self.config, position)
        self.assertFalse(rules.should_stop_loss())

    def test_take_profit_triggered(self):
        """Test when mark price falls below the take-profit threshold."""
        # Entry at $10, TP is 50%, so threshold is $5. Mark price is $4.
        position = create_mock_position("P1", "sell", 1, 10.0, 4.0)
        rules = MonitorRules(self.config, position)
        self.assertTrue(rules.should_take_profit())

    def test_take_profit_not_triggered(self):
        """Test when mark price is above the take-profit threshold."""
        # Entry at $10, TP threshold is $5. Mark price is $6.
        position = create_mock_position("P1", "sell", 1, 10.0, 6.0)
        rules = MonitorRules(self.config, position)
        self.assertFalse(rules.should_take_profit())

    def test_rules_do_not_apply_to_long_positions(self):
        """Test that SL/TP rules for short positions do not trigger for long positions."""
        # Long position that would otherwise trigger SL
        position = create_mock_position("C1", "buy", 1, 10.0, 21.0)
        rules = MonitorRules(self.config, position)
        self.assertFalse(rules.should_stop_loss())
        self.assertFalse(rules.should_take_profit())

    def test_zero_entry_price(self):
        """Test that rules do not trigger if entry price is zero to avoid errors."""
        position = create_mock_position("P1", "sell", 1, 0.0, 10.0)
        rules = MonitorRules(self.config, position)
        self.assertFalse(rules.should_stop_loss())
        self.assertFalse(rules.should_take_profit())

if __name__ == '__main__':
    unittest.main()
