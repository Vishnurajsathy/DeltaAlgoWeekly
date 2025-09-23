import unittest
import numpy as np

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analytics.volatility import calculate_historical_volatility, calculate_iv_rank

class TestVolatilityAnalytics(unittest.TestCase):
    """Unit tests for the volatility and IV Rank calculation functions."""

    def test_historical_volatility(self):
        """Test HV calculation with a sample data set."""
        # Prices with a known standard deviation of log returns
        prices = [100, 102, 101, 103, 102, 104, 103, 105]
        hv = calculate_historical_volatility(prices)
        # For this data, stdev of log returns is ~0.0145, sqrt(365) is ~19.1
        # Expected HV is ~0.2768
        self.assertAlmostEqual(hv, 0.2768, places=4)

    def test_hv_insufficient_data(self):
        """Test that HV returns 0 with insufficient data."""
        prices = [100]
        hv = calculate_historical_volatility(prices)
        self.assertEqual(hv, 0.0)

    def test_ivr_mid_rank(self):
        """Test IVR when current IV is in the middle of the range."""
        historical_ivs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        current_iv = 55.0
        # Expected: (55 - 10) / (100 - 10) = 45 / 90 = 0.5 -> 50%
        ivr = calculate_iv_rank(current_iv, historical_ivs)
        self.assertAlmostEqual(ivr, 50.0)

    def test_ivr_max_rank(self):
        """Test IVR when current IV is at the maximum of the historical range."""
        historical_ivs = [10, 20, 30, 40, 100]
        current_iv = 100.0
        ivr = calculate_iv_rank(current_iv, historical_ivs)
        self.assertAlmostEqual(ivr, 100.0)

    def test_ivr_min_rank(self):
        """Test IVR when current IV is at the minimum of the historical range."""
        historical_ivs = [10, 20, 30, 40, 100]
        current_iv = 10.0
        ivr = calculate_iv_rank(current_iv, historical_ivs)
        self.assertAlmostEqual(ivr, 0.0)

    def test_ivr_clamping(self):
        """Test that IVR correctly clamps values that are outside the historical range."""
        historical_ivs = [20.0, 80.0]
        # Test with current IV above the historical max
        self.assertAlmostEqual(calculate_iv_rank(100.0, historical_ivs), 100.0)
        # Test with current IV below the historical min
        self.assertAlmostEqual(calculate_iv_rank(10.0, historical_ivs), 0.0)

    def test_ivr_empty_history(self):
        """Test that IVR returns a sentinel error value with an empty historical series."""
        ivr = calculate_iv_rank(50.0, [])
        self.assertEqual(ivr, -1.0)

    def test_ivr_flat_history(self):
        """Test IVR when historical min and max are the same to avoid division by zero."""
        historical_ivs = [50.0, 50.0, 50.0]
        ivr = calculate_iv_rank(50.0, historical_ivs)
        self.assertEqual(ivr, 50.0)

if __name__ == '__main__':
    unittest.main()
