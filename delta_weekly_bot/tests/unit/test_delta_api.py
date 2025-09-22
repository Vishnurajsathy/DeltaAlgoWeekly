import unittest
from unittest.mock import patch, Mock
import requests

# Adjust path to allow importing from the 'src' directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.delta_api import DeltaAPIClient

# Create a dummy secrets class for testing purposes
class DummySecrets:
    def __init__(self):
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"

class TestDeltaAPIClient(unittest.TestCase):

    def setUp(self):
        """Set up a new DeltaAPIClient instance before each test."""
        self.secrets = DummySecrets()
        self.base_url = "https://test.api"
        self.client = DeltaAPIClient(secrets=self.secrets, base_url=self.base_url)

    @patch('requests.Session.request')
    def test_get_wallet_balances_success(self, mock_request):
        """
        Test successful fetching of wallet balances (an authenticated endpoint).
        """
        # Arrange: Configure the mock to return a successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_payload = {
            "success": True,
            "result": [
                {"asset_symbol": "USDT", "balance": "1000.0"},
                {"asset_symbol": "BTC", "balance": "0.1"}
            ]
        }
        mock_response.json.return_value = mock_payload
        mock_request.return_value = mock_response

        # Act: Call the method under test
        balances = self.client.get_wallet_balances()

        # Assert: Check that the data is parsed correctly and auth headers were sent
        self.assertEqual(len(balances), 2)
        self.assertEqual(balances[0]['asset_symbol'], 'USDT')
        mock_request.assert_called_once()

        sent_headers = mock_request.call_args.kwargs['headers']
        self.assertIn('api-key', sent_headers)
        self.assertIn('signature', sent_headers)
        self.assertIn('timestamp', sent_headers)
        self.assertEqual(sent_headers['api-key'], self.secrets.api_key)

    @patch('requests.Session.request')
    def test_get_wallet_balances_http_error(self, mock_request):
        """
        Test that the client handles HTTP errors gracefully.
        """
        # Arrange: Configure the mock to raise an HTTPError
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(text="Server Error"))

        # Act: Call the method
        balances = self.client.get_wallet_balances()

        # Assert: Check that the method returns an empty list on error
        self.assertEqual(balances, [])

    @patch('requests.Session.request')
    def test_get_options_chain_tickers_success(self, mock_request):
        """
        Test successful fetching of the options chain (a public endpoint).
        """
        # Arrange: Configure a successful mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_payload = {"success": True, "result": [{"symbol": "C-BTC-50000-251024"}]}
        mock_response.json.return_value = mock_payload
        mock_request.return_value = mock_response

        # Act
        tickers = self.client.get_options_chain_tickers("BTC", "25-10-2024")

        # Assert: Check the result and the request details
        self.assertEqual(len(tickers), 1)
        self.assertEqual(tickers[0]['symbol'], "C-BTC-50000-251024")

        # Assert that the correct URL and params were used
        call_pos_args, call_kwargs = mock_request.call_args

        # Check positional arguments (method, url)
        self.assertEqual(call_pos_args[0], 'GET')
        self.assertIn('/v2/tickers', call_pos_args[1])
        self.assertIn('contract_types=call_options%2Cput_options', call_pos_args[1])
        self.assertIn('underlying_asset_symbols=BTC', call_pos_args[1])
        self.assertIn('expiry_date=25-10-2024', call_pos_args[1])

        # Assert that NO auth headers were sent for this public endpoint
        sent_headers = call_kwargs['headers']
        self.assertNotIn('api-key', sent_headers)
        self.assertNotIn('signature', sent_headers)

if __name__ == '__main__':
    unittest.main()
