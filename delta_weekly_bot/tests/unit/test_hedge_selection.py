import unittest
from dataclasses import dataclass
from datetime import datetime

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.strategy.hedge import select_monthly_hedge_legs
from src.data.models import OptionsChain, Option
from src.utils.cfg import Config

# --- Mock Objects for Testing ---

@dataclass
class MockConfig:
    # No config is actually used by the hedge selection function,
    # but the function signature requires it.
    pass

def create_mock_option(symbol: str, o_type: str, strike: float) -> Option:
    """Helper function to create mock Option objects for testing."""
    return Option(
        instrument_id=hash(symbol),
        symbol=symbol,
        expiry=datetime.now(),
        strike=strike,
        option_type=o_type,
        best_bid=1.0,
        best_ask=2.0,
        last_price=1.5,
        greeks=None,
        open_interest=100
    )

class TestHedgeSelection(unittest.TestCase):
    """Unit tests for the monthly hedge selection logic."""

    def setUp(self):
        """Set up a default config and a base options chain for all tests."""
        self.config = MockConfig()
        self.chain = OptionsChain(
            underlying="BTC",
            expiry=datetime.now(),
            calls=[
                create_mock_option("C_49k", "call", 49000),
                create_mock_option("C_50k", "call", 50000),
                create_mock_option("C_51k", "call", 51000),
            ],
            puts=[
                create_mock_option("P_49k", "put", 49000),
                create_mock_option("P_50k", "put", 50000),
                create_mock_option("P_51k", "put", 51000),
            ]
        )

    def test_ideal_case_spot_on_strike(self):
        """Test finding the ATM straddle when spot is exactly on a strike."""
        atm_call, atm_put = select_monthly_hedge_legs(50000.0, self.chain, self.config)
        self.assertIsNotNone(atm_call)
        self.assertIsNotNone(atm_put)
        self.assertEqual(atm_call.strike, 50000)
        self.assertEqual(atm_put.strike, 50000)

    def test_spot_between_strikes_closer_to_higher(self):
        """Test finding the ATM straddle when spot is between two strikes (closer to higher)."""
        # Spot at 50600 is closer to 51000 than 50000
        atm_call, atm_put = select_monthly_hedge_legs(50600.0, self.chain, self.config)
        self.assertIsNotNone(atm_call)
        self.assertIsNotNone(atm_put)
        self.assertEqual(atm_call.strike, 51000)
        self.assertEqual(atm_put.strike, 51000)

    def test_spot_between_strikes_closer_to_lower(self):
        """Test finding the ATM straddle when spot is between two strikes (closer to lower)."""
        # Spot at 49400 is closer to 49000 than 50000
        atm_call, atm_put = select_monthly_hedge_legs(49400.0, self.chain, self.config)
        self.assertIsNotNone(atm_call)
        self.assertIsNotNone(atm_put)
        self.assertEqual(atm_call.strike, 49000)
        self.assertEqual(atm_put.strike, 49000)

    def test_empty_chain(self):
        """Test graceful handling of an empty options chain."""
        empty_chain = OptionsChain(underlying="BTC", expiry=datetime.now(), calls=[], puts=[])
        atm_call, atm_put = select_monthly_hedge_legs(50000.0, empty_chain, self.config)
        self.assertIsNone(atm_call)
        self.assertIsNone(atm_put)

    def test_inconsistent_chain_missing_put(self):
        """Test when an ATM strike is found, but a corresponding put is missing."""
        inconsistent_chain = OptionsChain(
            underlying="BTC", expiry=datetime.now(),
            calls=[create_mock_option("C_50k", "call", 50000)],
            puts=[]  # No puts
        )
        atm_call, atm_put = select_monthly_hedge_legs(50000.0, inconsistent_chain, self.config)
        self.assertIsNone(atm_call)
        self.assertIsNone(atm_put)

if __name__ == '__main__':
    unittest.main()
