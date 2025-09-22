import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

# --- Pydantic Models for Validation ---

class SymbolsConfig(BaseModel):
    underlying: str
    futures: str

class GeneralConfig(BaseModel):
    dry_run: bool
    base_ccy: str
    timezone: str
    poll_interval_seconds: int
    symbols: SymbolsConfig

class RiskConfig(BaseModel):
    max_margin_usage_pct: float
    max_daily_loss_pct: float
    max_weekly_loss_pct: float
    leg_stop_loss_pct: float
    take_profit_pct: float
    hard_kill_if_equity_drawdown_pct: float
    min_free_collateral_pct: float

class IVFilterConfig(BaseModel):
    min_ivr: int
    avoid_if_iv_spike_pct: int

class FiltersConfig(BaseModel):
    iv: IVFilterConfig
    atr_window: int
    avoid_big_event: bool
    weekend_size_reduction_pct: float

class EntryConfig(BaseModel):
    weekly_target_delta: List[float]
    min_credit_usdt_per_leg: float
    distance_sigma_min: float
    rebid_spread_bp: int

class DeltaHedgeFuturesConfig(BaseModel):
    enabled: bool
    rebalance_threshold: float
    max_futures_notional_vs_equity: float

class HedgeConfig(BaseModel):
    type: str
    notionals_ratio: float
    roll_days_before_expiry: int
    delta_hedge_futures: DeltaHedgeFuturesConfig

class AdjustmentsConfig(BaseModel):
    threaten_threshold_pct_from_strike: float
    roll_ahead_weeks: int
    put_call_recenter: bool
    widen_on_profit_lock: bool

class AlertOnConfig(BaseModel):
    margin_usage_exceeds_pct: float
    pnl_drawdown_pct: float
    iv_spike_pct: float

class MonitoringConfig(BaseModel):
    per_minute_chain: bool
    quadrant_window_minutes: int
    alert_on: AlertOnConfig

class DashboardConfig(BaseModel):
    enable: bool
    port: int
    auth: bool

class LoggingConfig(BaseModel):
    level: str
    to_file: bool
    file_path: str

class DeltaSecrets(BaseModel):
    api_key: str
    api_secret: str

class SecretsConfig(BaseModel):
    delta: Optional[DeltaSecrets] = None

class Config(BaseModel):
    general: GeneralConfig
    risk: RiskConfig
    filters: FiltersConfig
    entry: EntryConfig
    hedge: HedgeConfig
    adjustments: AdjustmentsConfig
    monitoring: MonitoringConfig
    dashboard: DashboardConfig
    logging: LoggingConfig
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)

def deep_merge_dicts(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merges d2 into d1.
    """
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            d1[k] = deep_merge_dicts(d1[k], v)
        else:
            d1[k] = v
    return d1

def load_config(config_dir: Path) -> Config:
    """
    Loads configuration from YAML files, merges them, and validates with Pydantic.

    Order of precedence (later files override earlier ones):
    1. default.yaml
    2. secrets.yaml (if it exists)
    """
    default_config_path = config_dir / "default.yaml"
    secrets_path = config_dir / "secrets.yaml"

    if not default_config_path.is_file():
        raise FileNotFoundError(f"Default config file not found at {default_config_path}")

    with open(default_config_path, 'r') as f:
        config_dict = yaml.safe_load(f)

    if secrets_path.is_file():
        with open(secrets_path, 'r') as f:
            secrets_dict = yaml.safe_load(f)
        # Nest secrets under a 'secrets' key to match the Pydantic model structure
        config_dict = deep_merge_dicts(config_dict, {"secrets": secrets_dict})

    return Config(**config_dict)
