import unittest
from dataclasses import dataclass
from datetime import datetime

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.strategy.rules import MonitorRules
from src.data.models import Position, Option, Greeks
# --- Mock Objects for Testing ---

@dataclass
class MockAdjustmentsConfig:
    threaten_threshold_pct_from_strike: float

@dataclass
class MockConfig:
    adjustments: MockAdjustmentsConfig

def create_mock_position_and_option(
    symbol: str, o_type: str, strike: float, side: str, size: float
) -> tuple[Position, Option]:
    """Helper function to create a matched pair of Position and Option objects."""
    pos = Position(
        instrument_id=hash(symbol),
        symbol=symbol,
        size=-size if side == 'sell' else size,
        side=side,
        entry_price=10.0,
        mark_price=12.0,
        unrealized_pnl=0,
        realized_pnl=0
    )
    opt = Option(
        instrument_id=hash(symbol),
        symbol=symbol,
        expiry=datetime.now(),
        strike=strike,
        option_type=o_type,
        best_bid=0, best_ask=0, last_price=0,
        greeks=None, open_interest=0
    )
    return pos, opt

class TestThreatDetectionRules(unittest.TestCase):
    """Unit tests for the is_leg_threatened rule."""

    def setUp(self):
        """Set up a default config for all tests."""
        self.config = MockConfig(
            adjustments=MockAdjustmentsConfig(
                threaten_threshold_pct_from_strike=5.0
            )
        )

    def test_call_threatened(self):
        """Test when spot price is within 5% of the short call strike."""
        # Strike is 100, threshold is 5%, so threat level is 100 * (1 - 0.05) = 95.
        # Spot at 96 should trigger the threat.
        pos, opt = create_mock_position_and_option("C1", "call", 100.0, "sell", 1)
        rules = MonitorRules(self.config, pos, spot_price=96.0, option_details=opt)
        self.assertTrue(rules.is_leg_threatened())

    def test_call_not_threatened(self):
        """Test when spot price is safely below the short call strike."""
        # Strike is 100, threat level is 95. Spot at 94 should be safe.
        pos, opt = create_mock_position_and_option("C1", "call", 100.0, "sell", 1)
        rules = MonitorRules(self.config, pos, spot_price=94.0, option_details=opt)
        self.assertFalse(rules.is_leg_threatened())

    def test_put_threatened(self):
        """Test when spot price is within 5% of the short put strike."""
        # Strike is 100, threshold is 5%, so threat level is 100 * (1 + 0.05) = 105.
        # Spot at 104 should trigger the threat.
        pos, opt = create_mock_position_and_option("P1", "put", 100.0, "sell", 1)
        rules = MonitorRules(self.config, pos, spot_price=104.0, option_details=opt)
        self.assertTrue(rules.is_leg_threatened())

    def test_put_not_threatened(self):
        """Test when spot price is safely above the short put strike."""
        # Strike is 100, threat level is 105. Spot at 106 should be safe.
        pos, opt = create_mock_position_and_option("P1", "put", 100.0, "sell", 1)
        rules = MonitorRules(self.config, pos, spot_price=106.0, option_details=opt)
        self.assertFalse(rules.is_leg_threatened())

    def test_rule_does_not_apply_to_long_positions(self):
        """Test that the threat rule does not trigger for long positions."""
        pos, opt = create_mock_position_and_option("C1", "call", 100.0, "buy", 1)
        rules = MonitorRules(self.config, pos, spot_price=96.0, option_details=opt)
        self.assertFalse(rules.is_leg_threatened())

if __name__ == '__main__':
    unittest.main()
