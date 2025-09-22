from datetime import datetime
from typing import Optional

from loguru import logger

from .delta_api import DeltaAPIClient
from .models import MarketDataSnapshot, OptionsChain, Option, Ticker, AccountInfo, Position, Greeks
from ..utils.cfg import Config
from ..utils.time import get_next_weekly_expiry, get_ist_time

class DataIngestor:
    """
    Responsible for fetching all required data from the API client
    and packaging it into a single, structured snapshot object.
    """
    def __init__(self, client: DeltaAPIClient, config: Config):
        self.client = client
        self.config = config
        logger.info("DataIngestor initialized.")

    def _map_ticker_to_option(self, ticker_data: dict, expiry_datetime: datetime) -> Option:
        """Maps a raw ticker dictionary from the API to our Option model."""
        greeks_data = ticker_data.get('greeks')
        greeks = None
        if greeks_data:
            greeks = Greeks(
                delta=float(greeks_data.get('delta', 0.0)),
                gamma=float(greeks_data.get('gamma', 0.0)),
                theta=float(greeks_data.get('theta', 0.0)),
                vega=float(greeks_data.get('vega', 0.0)),
                iv=float(ticker_data.get('mark_iv', 0.0))
            )

        return Option(
            instrument_id=ticker_data['product_id'],
            symbol=ticker_data['symbol'],
            expiry=expiry_datetime,
            strike=float(ticker_data['strike_price']),
            option_type=ticker_data['contract_type'].replace('_options', ''),
            best_bid=float(ticker_data.get('best_bid', 0.0)),
            best_ask=float(ticker_data.get('best_ask', 0.0)),
            last_price=float(ticker_data.get('close', 0.0)),
            greeks=greeks,
            open_interest=float(ticker_data.get('oi', 0.0))
        )

    def _map_balances_to_account_info(self, balances: list) -> Optional[AccountInfo]:
        """Finds the primary collateral balance and maps it to our AccountInfo model."""
        base_ccy = self.config.general.base_ccy
        for wallet in balances:
            if wallet.get('asset_symbol') == base_ccy:
                logger.debug(f"Found primary wallet for {base_ccy}.")
                # This is a simplified mapping. The API response is more complex.
                im = float(wallet.get('order_margin', 0.0)) + float(wallet.get('position_margin', 0.0))
                return AccountInfo(
                    username="N/A",  # Not available in this endpoint
                    equity=float(wallet.get('balance', 0.0)),
                    balance=float(wallet.get('balance', 0.0)),
                    free_collateral=float(wallet.get('available_balance', 0.0)),
                    margin_balance=float(wallet.get('balance', 0.0)),
                    initial_margin=im,
                    maintenance_margin=float(wallet.get('position_margin', 0.0)) # Simplified
                )
        logger.warning(f"Could not find wallet balance for base currency {base_ccy}")
        return None

    def fetch_all(self) -> MarketDataSnapshot:
        """
        Fetches all data points and returns a consolidated MarketDataSnapshot.
        """
        logger.info("--- Starting Data Ingestion Cycle ---")

        # 1. Fetch account and position data (authenticated)
        balances = self.client.get_wallet_balances()
        positions_raw = self.client.get_all_positions()

        # 2. Fetch market data (public)
        target_expiry_date = get_next_weekly_expiry()
        target_expiry_datetime = datetime.combine(target_expiry_date, datetime.min.time())

        chain_tickers = self.client.get_options_chain_tickers(
            underlying_asset=self.config.general.symbols.underlying.replace('USDT', ''),
            expiry_date=target_expiry_date.strftime('%d-%m-%Y')
        )

        futures_ticker_raw = self.client.get_ticker(self.config.general.symbols.futures)

        # 3. Process and map data to our Pydantic models
        account_info = self._map_balances_to_account_info(balances)

        positions = [Position(**p) for p in positions_raw]

        calls = [self._map_ticker_to_option(t, target_expiry_datetime) for t in chain_tickers if t['contract_type'] == 'call_options']
        puts = [self._map_ticker_to_option(t, target_expiry_datetime) for t in chain_tickers if t['contract_type'] == 'put_options']
        options_chain = OptionsChain(
            underlying=self.config.general.symbols.underlying,
            expiry=target_expiry_datetime,
            calls=calls,
            puts=puts
        )

        futures_ticker = Ticker(**futures_ticker_raw) if futures_ticker_raw else None

        snapshot = MarketDataSnapshot(
            timestamp=get_ist_time(),
            account_info=account_info,
            positions=positions,
            options_chain=options_chain,
            futures_ticker=futures_ticker
        )

        logger.info("--- Data Ingestion Cycle Complete ---")
        return snapshot
