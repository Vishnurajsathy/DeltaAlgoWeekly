import unittest
from dataclasses import dataclass
from typing import List
from datetime import datetime

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analytics.strikes import select_new_leg_for_roll
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

class TestRollSelection(unittest.TestCase):
    """Unit tests for the select_new_leg_for_roll function."""

    def setUp(self):
        """Set up a default config and a base options chain for all tests."""
        self.config = MockConfig(
            entry=MockEntryConfig(
                weekly_target_delta=[0.08, 0.12],
                min_credit_usdt_per_leg=10.0
            )
        )
        self.chain = OptionsChain(
            underlying="BTC",
            expiry=datetime.now(),
            calls=[
                create_mock_option("C_50k", "call", 50000, 0.15, 20),
                create_mock_option("C_51k", "call", 51000, 0.10, 15), # Meets criteria
                create_mock_option("C_52k", "call", 52000, 0.09, 12), # Meets criteria
            ],
            puts=[
                create_mock_option("P_49k", "put", 49000, -0.09, 12), # Meets criteria
                create_mock_option("P_48k", "put", 48000, -0.10, 15), # Meets criteria
                create_mock_option("P_47k", "put", 47000, -0.15, 20),
            ]
        )

    def test_successful_call_roll_selects_closest(self):
        """Test finding a valid roll for a threatened call and selecting the closest strike."""
        threatened_call = create_mock_option("C_Threat", "call", 50500, 0.13, 18)
        # Both C_51k and C_52k are valid rolls. The logic should pick the closest one, which is C_51k.
        self.chain.calls.append(threatened_call)

        new_leg = select_new_leg_for_roll(threatened_call, self.chain, self.config)
        self.assertIsNotNone(new_leg)
        self.assertEqual(new_leg.symbol, "C_51k")

    def test_successful_put_roll_selects_closest(self):
        """Test finding a valid roll for a threatened put and selecting the closest strike."""
        threatened_put = create_mock_option("P_Threat", "put", 48500, -0.13, 18)
        # Both P_48k and P_49k are valid rolls. The logic should pick the closest one, which is P_48k.
        self.chain.puts.append(threatened_put)

        new_leg = select_new_leg_for_roll(threatened_put, self.chain, self.config)
        self.assertIsNotNone(new_leg)
        self.assertEqual(new_leg.symbol, "P_48k")

    def test_no_roll_further_otm(self):
        """Test when no strikes are available further OTM."""
        threatened_call = create_mock_option("C_Threat", "call", 53000, 0.08, 11)
        self.chain.calls.append(threatened_call)

        new_leg = select_new_leg_for_roll(threatened_call, self.chain, self.config)
        self.assertIsNone(new_leg)

    def test_no_roll_insufficient_credit(self):
        """Test when further strikes exist but have insufficient credit."""
        self.config.entry.min_credit_usdt_per_leg = 100 # Set an impossibly high credit requirement
        threatened_call = create_mock_option("C_Threat", "call", 50500, 0.13, 18)
        self.chain.calls.append(threatened_call)

        new_leg = select_new_leg_for_roll(threatened_call, self.chain, self.config)
        self.assertIsNone(new_leg)

    def test_no_roll_delta_mismatch(self):
        """Test when further strikes exist but do not match delta criteria."""
        self.config.entry.weekly_target_delta = [0.18, 0.20] # Look for high delta options
        threatened_call = create_mock_option("C_Threat", "call", 49000, 0.25, 30)
        self.chain.calls.append(threatened_call)

        new_leg = select_new_leg_for_roll(threatened_call, self.chain, self.config)
        self.assertIsNone(new_leg)

if __name__ == '__main__':
    unittest.main()
