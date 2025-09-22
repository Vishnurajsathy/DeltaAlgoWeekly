import unittest
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analytics.strikes import select_short_strangle_legs
from src.data.models import OptionsChain, Option, Greeks

# --- Mock Objects for Testing ---

@dataclass
class MockEntryConfig:
    weekly_target_delta: List[float]
    min_credit_usdt_per_leg: float

@dataclass
class MockConfig:
    entry: MockEntryConfig

def create_mock_option(symbol: str, o_type: str, strike: float, delta: float, bid: float) -> Option:
    """Helper function to create mock Option objects for testing."""
    return Option(
        instrument_id=hash(symbol),
        symbol=symbol,
        expiry=datetime.now(),
        strike=strike,
        option_type=o_type,
        best_bid=bid,
        best_ask=bid + 0.1,
        last_price=bid,
        greeks=Greeks(delta=delta, gamma=0.01, theta=-0.5, vega=0.2, iv=0.5),
        open_interest=100
    )

class TestStrikeSelection(unittest.TestCase):
    """Unit tests for the strike selection logic."""

    def setUp(self):
        """Set up a default config object for all tests."""
        self.config = MockConfig(
            entry=MockEntryConfig(
                weekly_target_delta=[0.08, 0.12],
                min_credit_usdt_per_leg=10.0
            )
        )

    def test_ideal_case(self):
        """Test the ideal scenario where a perfect pair is found."""
        chain = OptionsChain(
            underlying="BTC",
            expiry=datetime.now(),
            calls=[
                create_mock_option("C1", "call", 50000, 0.15, 20),
                create_mock_option("C2", "call", 51000, 0.10, 15),  # Correct one
                create_mock_option("C3", "call", 52000, 0.07, 12),
            ],
            puts=[
                create_mock_option("P1", "put", 49000, -0.07, 12),
                create_mock_option("P2", "put", 48000, -0.10, 15),  # Correct one
                create_mock_option("P3", "put", 47000, -0.15, 20),
            ]
        )

        call, put = select_short_strangle_legs(chain, self.config)
        self.assertIsNotNone(call)
        self.assertIsNotNone(put)
        self.assertEqual(call.symbol, "C2")
        self.assertEqual(put.symbol, "P2")

    def test_no_suitable_delta(self):
        """Test when no options are in the target delta range."""
        chain = OptionsChain(
            underlying="BTC", expiry=datetime.now(),
            calls=[create_mock_option("C1", "call", 51000, 0.20, 15)],
            puts=[create_mock_option("P1", "put", 48000, -0.20, 15)]
        )
        call, put = select_short_strangle_legs(chain, self.config)
        self.assertIsNone(call)
        self.assertIsNone(put)

    def test_insufficient_credit(self):
        """Test when deltas match but the premium is too low."""
        chain = OptionsChain(
            underlying="BTC", expiry=datetime.now(),
            calls=[create_mock_option("C1", "call", 51000, 0.10, 5)],  # Credit too low
            puts=[create_mock_option("P1", "put", 48000, -0.10, 5)]   # Credit too low
        )
        call, put = select_short_strangle_legs(chain, self.config)
        self.assertIsNone(call)
        self.assertIsNone(put)

    def test_selects_farthest_otm_when_multiple_qualify(self):
        """Test that the farthest OTM option is chosen when multiple options are eligible."""
        chain = OptionsChain(
            underlying="BTC", expiry=datetime.now(),
            calls=[
                create_mock_option("C1", "call", 51000, 0.11, 15),  # Qualifies
                create_mock_option("C2", "call", 52000, 0.09, 12)   # Qualifies, should be chosen
            ],
            puts=[
                create_mock_option("P1", "put", 48000, -0.09, 12),  # Qualifies, should be chosen
                create_mock_option("P2", "put", 49000, -0.11, 15)   # Qualifies
            ]
        )
        call, put = select_short_strangle_legs(chain, self.config)
        self.assertEqual(call.symbol, "C2")
        self.assertEqual(put.symbol, "P1")

    def test_one_leg_missing(self):
        """Test when only one suitable leg can be found."""
        chain = OptionsChain(
            underlying="BTC", expiry=datetime.now(),
            calls=[create_mock_option("C1", "call", 51000, 0.10, 15)], # Suitable call
            puts=[create_mock_option("P1", "put", 48000, -0.20, 15)]  # No suitable put
        )
        call, put = select_short_strangle_legs(chain, self.config)
        self.assertIsNotNone(call)
        self.assertIsNone(put)
        self.assertEqual(call.symbol, "C1")

if __name__ == '__main__':
    unittest.main()
