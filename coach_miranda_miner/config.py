from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    trading_mode: str
    data_mode: str
    analyzer_mode: str
    discovery_mode: str
    openai_model: str
    coinmarketcap_api_key: str | None
    cryptopanic_api_key: str | None
    coinalyze_api_key: str | None
    coinglass_api_key: str | None
    exchange_ids: list[str]
    exchange_id: str
    symbol: str
    quote_currency: str
    timeframe: str
    timeframes: list[str]
    candle_limit: int
    discovery_limit: int
    discovery_pool_limit: int
    min_market_cap_usd: float
    oi_bases: list[str]
    oi_limit: int
    scan_interval_seconds: int
    render_charts: bool
    chart_dir: str
    short_ma: int
    long_ma: int
    rsi_period: int
    rsi_buy_max: float
    rsi_sell_min: float
    starting_cash: float
    max_position_usd: float
    max_daily_loss_usd: float
    btc_kill_switch_drop_pct: float
    min_volume_24h_usd: float
    min_risk_reward: float
    min_confidence: float
    max_stop_atr_multiple: float
    backtest_fee_bps: float
    backtest_slippage_bps: float
    backtest_stop_atr_multiple: float
    backtest_target_r_multiple: float
    journal_db: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    telegram_min_signal: str
    alert_cooldown_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            trading_mode=os.getenv("TRADING_MODE", "paper").lower(),
            data_mode=os.getenv("DATA_MODE", "coinbase").lower(),
            analyzer_mode=os.getenv("ANALYZER_MODE", "rule").lower(),
            discovery_mode=os.getenv("DISCOVERY_MODE", "exchange").lower(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            coinmarketcap_api_key=_optional(os.getenv("COINMARKETCAP_API_KEY")),
            cryptopanic_api_key=_optional(os.getenv("CRYPTOPANIC_API_KEY")),
            coinalyze_api_key=_optional(os.getenv("COINALYZE_API_KEY")),
            coinglass_api_key=_optional(os.getenv("COINGLASS_API_KEY")),
            exchange_ids=_csv(os.getenv("EXCHANGE_IDS", "binance,bybit,okx")),
            exchange_id=os.getenv("EXCHANGE_ID", "binance"),
            symbol=os.getenv("SYMBOL", "BTC/USDT"),
            quote_currency=os.getenv("QUOTE_CURRENCY", "USDT"),
            timeframe=os.getenv("TIMEFRAME", "1h"),
            timeframes=_csv(os.getenv("TIMEFRAMES", "1d,4h,1h,15m")),
            candle_limit=int(os.getenv("CANDLE_LIMIT", "200")),
            discovery_limit=int(os.getenv("DISCOVERY_LIMIT", "5")),
            discovery_pool_limit=int(os.getenv("DISCOVERY_POOL_LIMIT", "100")),
            min_market_cap_usd=float(os.getenv("MIN_MARKET_CAP_USD", "100000000")),
            oi_bases=_csv(os.getenv("OI_BASES", "BTC,ETH,SOL,XRP,DOGE,ADA,AVAX,LINK,DOT")),
            oi_limit=int(os.getenv("OI_LIMIT", "8")),
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "900")),
            render_charts=_bool(os.getenv("RENDER_CHARTS", "true")),
            chart_dir=os.getenv("CHART_DIR", "charts"),
            short_ma=int(os.getenv("SHORT_MA", "20")),
            long_ma=int(os.getenv("LONG_MA", "50")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            rsi_buy_max=float(os.getenv("RSI_BUY_MAX", "65")),
            rsi_sell_min=float(os.getenv("RSI_SELL_MIN", "35")),
            starting_cash=float(os.getenv("STARTING_CASH", "10000")),
            max_position_usd=float(os.getenv("MAX_POSITION_USD", "1000")),
            max_daily_loss_usd=float(os.getenv("MAX_DAILY_LOSS_USD", "250")),
            btc_kill_switch_drop_pct=float(os.getenv("BTC_KILL_SWITCH_DROP_PCT", "3")),
            min_volume_24h_usd=float(os.getenv("MIN_VOLUME_24H_USD", "50000000")),
            min_risk_reward=float(os.getenv("MIN_RISK_REWARD", "2.0")),
            min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.72")),
            max_stop_atr_multiple=float(os.getenv("MAX_STOP_ATR_MULTIPLE", "3")),
            backtest_fee_bps=float(os.getenv("BACKTEST_FEE_BPS", "10")),
            backtest_slippage_bps=float(os.getenv("BACKTEST_SLIPPAGE_BPS", "5")),
            backtest_stop_atr_multiple=float(os.getenv("BACKTEST_STOP_ATR_MULTIPLE", "1.5")),
            backtest_target_r_multiple=float(os.getenv("BACKTEST_TARGET_R_MULTIPLE", "2")),
            journal_db=os.getenv("JOURNAL_DB", "coach_miranda_miner.sqlite3"),
            telegram_bot_token=_optional(os.getenv("TELEGRAM_BOT_TOKEN")),
            telegram_chat_id=_optional(os.getenv("TELEGRAM_CHAT_ID")),
            telegram_min_signal=os.getenv("TELEGRAM_MIN_SIGNAL", "enter").lower(),
            alert_cooldown_minutes=int(os.getenv("ALERT_COOLDOWN_MINUTES", "180")),
        )


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()
