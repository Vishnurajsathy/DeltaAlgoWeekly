import time
import hmac
import hashlib
import json
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

import requests
from loguru import logger

# A placeholder for the config object that will be passed in.
# This avoids a circular import with the main cfg.py but allows for type hinting.
class DeltaSecrets:
    api_key: str
    api_secret: str

class DeltaAPIClient:
    """
    A custom API client for Delta Exchange V2 REST API.
    This client handles request signing and provides methods for required endpoints.
    """

    def __init__(self, secrets: DeltaSecrets, base_url: str):
        if not secrets or not hasattr(secrets, 'api_key') or not hasattr(secrets, 'api_secret'):
            raise ValueError("Delta API secrets are not configured correctly.")

        self.api_key = secrets.api_key
        self.api_secret = secrets.api_secret
        self.base_url = base_url
        self.session = requests.Session()
        logger.info(f"Initialized DeltaAPIClient for base URL: {self.base_url}")

    def _generate_signature(self, method: str, path: str, query_params: str = "", payload: str = "") -> tuple[str, str]:
        """Generates the required HMAC-SHA256 signature for a request."""
        timestamp = str(int(time.time()))
        signature_data = method + timestamp + path + query_params + payload

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature, timestamp

    def _send_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """A generic method to send signed requests to the Delta API."""
        query_string = f"?{urlencode(params)}" if params else ""
        payload_string = json.dumps(data) if data else ""

        # Public endpoints do not require a signature
        is_public = not self.api_key or not self.api_secret

        headers = {
            'User-Agent': 'delta-weekly-bot/0.1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        if not is_public:
            signature, timestamp = self._generate_signature(method, path, query_string, payload_string)
            headers['api-key'] = self.api_key
            headers['signature'] = signature
            headers['timestamp'] = timestamp

        url = self.base_url + path + query_string

        try:
            logger.debug(f"Sending {method} request to {url} with data: {payload_string}")
            response = self.session.request(method, url, headers=headers, data=payload_string, timeout=10)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            response_json = response.json()
            if 'error' in response_json or response_json.get('success') is False:
                logger.error(f"API call to {path} returned an error: {response_json}")
                return {}

            logger.debug(f"Successfully received response from {path}")
            return response_json

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - {http_err.response.text}")
        except Exception as e:
            logger.exception(f"An error occurred during API request to {path}: {e}")

        return {}

    # --- Public Methods ---

    def get_wallet_balances(self) -> List[dict]:
        """Fetches all wallet balances. Requires authentication."""
        response = self._send_request("GET", "/v2/wallet/balances")
        return response.get('result', [])

    def get_all_positions(self) -> List[dict]:
        """Fetches all margined positions. Requires authentication."""
        response = self._send_request("GET", "/v2/positions/margined")
        return response.get('result', [])

    def get_options_chain_tickers(self, underlying_asset: str, expiry_date: str) -> List[dict]:
        """
        Fetches the option chain for a given underlying and expiry date (DD-MM-YYYY).
        This is a public endpoint and does not require authentication.
        """
        params = {
            'contract_types': 'call_options,put_options',
            'underlying_asset_symbols': underlying_asset,
            'expiry_date': expiry_date
        }
        # This is a public endpoint, so we can send a request without signing.
        # Temporarily disable auth for this call for simplicity.
        # A better implementation would be to have a separate public_request method.
        original_key, original_secret = self.api_key, self.api_secret
        self.api_key, self.api_secret = None, None
        response = self._send_request("GET", "/v2/tickers", params=params)
        self.api_key, self.api_secret = original_key, original_secret

        return response.get('result', [])

    def get_products(self, page_size: int = 100) -> List[dict]:
        """
        Fetches all available products/instruments. Public endpoint.
        """
        params = {'page_size': page_size}
        original_key, original_secret = self.api_key, self.api_secret
        self.api_key, self.api_secret = None, None
        response = self._send_request("GET", "/v2/products", params=params)
        self.api_key, self.api_secret = original_key, original_secret
        return response.get('result', [])

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches the ticker data for a specific product symbol.
        This is a public endpoint.
        """
        path = f"/v2/tickers/{symbol}"
        original_key, original_secret = self.api_key, self.api_secret
        self.api_key, self.api_secret = None, None
        response = self._send_request("GET", path)
        self.api_key, self.api_secret = original_key, original_secret

        return response.get('result', {})
