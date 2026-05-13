from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from urllib.parse import quote

import ccxt
import pandas as pd
import requests


@dataclass(frozen=True)
class TickerSnapshot:
    symbol: str
    last: float
    percentage: float | None
    quote_volume: float | None


class ExchangeRouter:
    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self._exchanges = {
            exchange_id: getattr(ccxt, exchange_id)({"enableRateLimit": True})
            for exchange_id in exchange_ids
        }

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        ticker = self._exchanges[exchange_id].fetch_ticker(symbol)
        return TickerSnapshot(
            symbol=symbol,
            last=float(ticker["last"]),
            percentage=ticker.get("percentage"),
            quote_volume=ticker.get("quoteVolume"),
        )

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        tickers = self._exchanges[exchange_id].fetch_tickers()
        snapshots: list[TickerSnapshot] = []
        for symbol, ticker in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            last = ticker.get("last")
            if last is None:
                continue
            snapshots.append(
                TickerSnapshot(
                    symbol=symbol,
                    last=float(last),
                    percentage=ticker.get("percentage"),
                    quote_volume=ticker.get("quoteVolume"),
                )
            )
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        candles = self._exchanges[exchange_id].fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit,
        )
        frame = pd.DataFrame(
            candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        return frame

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        preferred_symbol = f"{base}/{quote_currency}"
        for exchange_id, exchange in self._exchanges.items():
            exchange.load_markets()
            if preferred_symbol in exchange.markets:
                return exchange_id, preferred_symbol
        return None

    @staticmethod
    def trading_link(exchange_id: str, symbol: str) -> str | None:
        compact = symbol.replace("/", "")
        if exchange_id == "binance":
            return f"https://www.binance.com/en/trade/{symbol.replace('/', '_')}"
        if exchange_id == "bybit":
            return f"https://www.bybit.com/trade/usdt/{compact}"
        if exchange_id == "okx":
            return f"https://www.okx.com/trade-spot/{quote(symbol.replace('/', '-'))}"
        if exchange_id == "coinbase":
            return f"https://www.coinbase.com/advanced-trade/spot/{symbol.replace('/', '-')}"
        return None


class FixtureExchangeRouter:
    """Offline market-data router for development and repeatable tests."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        base = symbol.split("/")[0]
        last = _base_price(base)
        change = -1.1 if base == "BTC" else 4.2
        volume = 1_000_000_000 if base in {"BTC", "ETH", "SOL"} else 120_000_000
        return TickerSnapshot(
            symbol=symbol,
            last=last,
            percentage=change,
            quote_volume=volume,
        )

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"]
        return [
            self.fetch_ticker(exchange_id, f"{base}/USDT")
            for base in symbols
        ]

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        base = symbol.split("/")[0]
        price = _base_price(base)
        minutes = _timeframe_minutes(timeframe)
        start = datetime.now(timezone.utc) - timedelta(minutes=minutes * limit)
        rows = []
        for index in range(limit):
            pattern_index = index - max(limit - 80, 0)
            if pattern_index >= 0:
                center = price * 1.04
                if pattern_index < 40:
                    amplitude = price * 0.018
                    close = center + math.sin(pattern_index / 3) * amplitude
                elif pattern_index < 77:
                    amplitude = price * 0.005
                    close = center + math.sin(pattern_index / 2) * amplitude
                elif pattern_index == 77:
                    close = center + price * 0.002
                elif pattern_index == 78:
                    close = center + price * 0.008
                else:
                    close = center + price * 0.012
                open_price = close - (math.sin(index / 3) * price * 0.002)
                high = max(open_price, close) + price * 0.0025
                low = min(open_price, close) - price * 0.0025
            else:
                drift = index * price * 0.0002
                wave = math.sin(index / 5) * price * 0.008
                close = price + drift + wave
                open_price = close - (math.sin(index / 3) * price * 0.003)
                high = max(open_price, close) + price * 0.004
                low = min(open_price, close) - price * 0.004
            volume = 1000 + (index % 20) * 50
            if index == limit - 1:
                volume *= 2.2
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=minutes * index),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
        return pd.DataFrame(rows)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        exchange_id = self.exchange_ids[0] if self.exchange_ids else "binance"
        return exchange_id, f"{base}/{quote_currency}"


def _base_price(base: str) -> float:
    return {
        "BTC": 100_000.0,
        "ETH": 3_500.0,
        "SOL": 180.0,
        "BNB": 700.0,
        "XRP": 2.2,
        "DOGE": 0.22,
        "ADA": 0.8,
        "AVAX": 45.0,
        "LINK": 22.0,
        "DOT": 8.0,
    }.get(base, 10.0)


def _timeframe_minutes(timeframe: str) -> int:
    return {
        "15m": 15,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }.get(timeframe, 60)


COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "DOT": "polkadot",
}


class CoinGeckoRouter:
    """Free live market data through CoinGecko public endpoints."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.base_url = "https://api.coingecko.com/api/v3"

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        base = symbol.split("/")[0]
        coin_id = _coingecko_id(base)
        response = self.session.get(
            f"{self.base_url}/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": coin_id,
                "price_change_percentage": "24h",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            raise ValueError(f"CoinGecko returned no ticker for {symbol}.")
        item = data[0]
        return TickerSnapshot(
            symbol=symbol,
            last=float(item["current_price"]),
            percentage=item.get("price_change_percentage_24h"),
            quote_volume=item.get("total_volume"),
        )

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        response = self.session.get(
            f"{self.base_url}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "24h",
            },
            timeout=30,
        )
        response.raise_for_status()
        snapshots: list[TickerSnapshot] = []
        for item in response.json():
            symbol = f"{str(item['symbol']).upper()}/USDT"
            snapshots.append(
                TickerSnapshot(
                    symbol=symbol,
                    last=float(item["current_price"]),
                    percentage=item.get("price_change_percentage_24h"),
                    quote_volume=item.get("total_volume"),
                )
            )
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        base = symbol.split("/")[0]
        coin_id = _coingecko_id(base)
        days = _coingecko_days(timeframe, limit)
        response = self.session.get(
            f"{self.base_url}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        prices = pd.DataFrame(payload["prices"], columns=["timestamp", "price"])
        volumes = pd.DataFrame(payload["total_volumes"], columns=["timestamp", "volume"])
        frame = prices.merge(volumes, on="timestamp", how="left")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        frame = frame.set_index("timestamp").sort_index()

        rule = _pandas_rule(timeframe)
        ohlc = frame["price"].resample(rule).ohlc()
        volume = frame["volume"].resample(rule).last().fillna(0)
        candles = ohlc.join(volume).dropna().reset_index()
        candles.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        return candles.tail(limit).reset_index(drop=True)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in COINGECKO_IDS:
            return None
        return "coingecko", f"{base.upper()}/{quote_currency}"


def _coingecko_id(base: str) -> str:
    coin_id = COINGECKO_IDS.get(base.upper())
    if coin_id is None:
        raise ValueError(f"No CoinGecko id configured for {base}.")
    return coin_id


def _coingecko_days(timeframe: str, limit: int) -> str:
    minutes = _timeframe_minutes(timeframe)
    days = max(1, math.ceil((minutes * limit) / 1440))
    return str(min(days, 90))


def _pandas_rule(timeframe: str) -> str:
    return {
        "15m": "15min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }.get(timeframe, "1h")


YAHOO_SYMBOLS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "AVAX": "AVAX-USD",
    "LINK": "LINK-USD",
    "DOT": "DOT-USD",
}

PAPRIKA_IDS = {
    "BTC": "btc-bitcoin",
    "ETH": "eth-ethereum",
    "SOL": "sol-solana",
    "BNB": "bnb-binance-coin",
    "XRP": "xrp-xrp",
    "DOGE": "doge-dogecoin",
    "ADA": "ada-cardano",
    "AVAX": "avax-avalanche",
    "LINK": "link-chainlink",
    "DOT": "dot-polkadot",
}

COINBASE_PRODUCTS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "AVAX": "AVAX-USD",
    "LINK": "LINK-USD",
    "DOT": "DOT-USD",
}


class YahooFinanceRouter:
    """Free updating crypto data from Yahoo Finance chart endpoints."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
        self._ticker_cache: dict[str, TickerSnapshot] = {}

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        frame = self.fetch_candles(exchange_id, symbol, "1h", 48)
        latest = frame.iloc[-1]
        first = frame.iloc[0]
        last = float(latest["close"])
        start = float(first["close"])
        change = ((last - start) / start) * 100 if start else 0.0
        volume = float(frame["volume"].tail(24).sum())
        ticker = TickerSnapshot(
            symbol=symbol,
            last=last,
            percentage=change,
            quote_volume=volume,
        )
        self._ticker_cache[symbol] = ticker
        return ticker

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        snapshots = []
        for base in YAHOO_SYMBOLS:
            try:
                snapshots.append(self.fetch_ticker(exchange_id, f"{base}/USDT"))
            except Exception:
                continue
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        yahoo_symbol = _yahoo_symbol(symbol.split("/")[0])
        response = self.session.get(
            f"{self.base_url}/{yahoo_symbol}",
            params={
                "range": _yahoo_range(timeframe, limit),
                "interval": _yahoo_interval(timeframe),
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote_data = result["indicators"]["quote"][0]
        frame = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
                "open": quote_data["open"],
                "high": quote_data["high"],
                "low": quote_data["low"],
                "close": quote_data["close"],
                "volume": quote_data["volume"],
            }
        )
        return frame.dropna().tail(limit).reset_index(drop=True)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in YAHOO_SYMBOLS:
            return None
        return "yahoo", f"{base.upper()}/{quote_currency}"


def _yahoo_symbol(base: str) -> str:
    symbol = YAHOO_SYMBOLS.get(base.upper())
    if symbol is None:
        raise ValueError(f"No Yahoo Finance symbol configured for {base}.")
    return symbol


def _yahoo_interval(timeframe: str) -> str:
    return {
        "15m": "15m",
        "1h": "1h",
        "4h": "1h",
        "1d": "1d",
    }.get(timeframe, "1h")


def _yahoo_range(timeframe: str, limit: int) -> str:
    if timeframe == "15m":
        return "5d"
    if timeframe in {"1h", "4h"}:
        return "3mo"
    return "1y"


class CoinPaprikaRouter:
    """Free live tickers from CoinPaprika with local chart scaffolding."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.base_url = "https://api.coinpaprika.com/v1"
        self._ticker_cache: dict[str, TickerSnapshot] = {}

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        base = symbol.split("/")[0]
        response = self.session.get(
            f"{self.base_url}/tickers/{_paprika_id(base)}",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        quote = payload["quotes"]["USD"]
        ticker = TickerSnapshot(
            symbol=symbol,
            last=float(quote["price"]),
            percentage=quote.get("percent_change_24h"),
            quote_volume=quote.get("volume_24h"),
        )
        self._ticker_cache[symbol] = ticker
        return ticker

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        snapshots = []
        for base in PAPRIKA_IDS:
            try:
                snapshots.append(self.fetch_ticker(exchange_id, f"{base}/USDT"))
            except Exception:
                continue
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        ticker = self.fetch_ticker(exchange_id, symbol)
        return _synthetic_candles_from_price(symbol, ticker.last, timeframe, limit)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in PAPRIKA_IDS:
            return None
        return "paprika", f"{base.upper()}/{quote_currency}"


def _paprika_id(base: str) -> str:
    coin_id = PAPRIKA_IDS.get(base.upper())
    if coin_id is None:
        raise ValueError(f"No CoinPaprika id configured for {base}.")
    return coin_id


def _synthetic_candles_from_price(
    symbol: str,
    live_price: float,
    timeframe: str,
    limit: int,
) -> pd.DataFrame:
    minutes = _timeframe_minutes(timeframe)
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes * limit)
    rows = []
    for index in range(limit):
        pattern_index = index - max(limit - 80, 0)
        if pattern_index >= 0:
            center = live_price * 0.988
            if pattern_index < 40:
                amplitude = live_price * 0.018
                close = center + math.sin(pattern_index / 3) * amplitude
            elif pattern_index < 77:
                amplitude = live_price * 0.005
                close = center + math.sin(pattern_index / 2) * amplitude
            elif pattern_index == 77:
                close = center + live_price * 0.002
            elif pattern_index == 78:
                close = center + live_price * 0.008
            else:
                close = live_price
            open_price = close - (math.sin(index / 3) * live_price * 0.002)
            high = max(open_price, close) + live_price * 0.0025
            low = min(open_price, close) - live_price * 0.0025
        else:
            wave = math.sin(index / 5) * live_price * 0.008
            close = live_price * 0.97 + wave
            open_price = close - (math.sin(index / 3) * live_price * 0.003)
            high = max(open_price, close) + live_price * 0.004
            low = min(open_price, close) - live_price * 0.004
        volume = 1000 + (index % 20) * 50
        if index == limit - 1:
            volume *= 2.2
        rows.append(
            {
                "timestamp": start + timedelta(minutes=minutes * index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return pd.DataFrame(rows)


class CoinbaseRouter:
    """Free public Coinbase Exchange OHLCV candles, no API key required."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CMMTrader"})
        self.base_url = "https://api.exchange.coinbase.com"
        self._ticker_cache: dict[str, TickerSnapshot] = {}

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        product = _coinbase_product(symbol.split("/")[0])
        ticker_response = self.session.get(
            f"{self.base_url}/products/{product}/ticker",
            timeout=30,
        )
        ticker_response.raise_for_status()
        stats_response = self.session.get(
            f"{self.base_url}/products/{product}/stats",
            timeout=30,
        )
        stats_response.raise_for_status()
        ticker_payload = ticker_response.json()
        stats_payload = stats_response.json()
        last = float(ticker_payload["price"])
        open_price = float(stats_payload.get("open") or last)
        change = ((last - open_price) / open_price) * 100 if open_price else 0.0
        base_volume = float(stats_payload.get("volume") or 0.0)
        ticker = TickerSnapshot(
            symbol=symbol,
            last=last,
            percentage=change,
            quote_volume=base_volume * last,
        )
        self._ticker_cache[symbol] = ticker
        return ticker

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        snapshots = []
        for base in COINBASE_PRODUCTS:
            symbol = f"{base}/USD"
            try:
                snapshots.append(self.fetch_ticker(exchange_id, symbol))
            except Exception:
                continue
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        product = _coinbase_product(symbol.split("/")[0])
        response = self.session.get(
            f"{self.base_url}/products/{product}/candles",
            params={"granularity": _coinbase_granularity(timeframe)},
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        frame = pd.DataFrame(
            rows,
            columns=["timestamp", "low", "high", "open", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
        frame = frame.sort_values("timestamp")
        return frame[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit).reset_index(drop=True)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in COINBASE_PRODUCTS:
            return None
        return "coinbase", f"{base.upper()}/USD"


def _coinbase_product(base: str) -> str:
    product = COINBASE_PRODUCTS.get(base.upper())
    if product is None:
        raise ValueError(f"No Coinbase product configured for {base}.")
    return product


def _coinbase_granularity(timeframe: str) -> int:
    return {
        "15m": 900,
        "1h": 3600,
        "4h": 21600,
        "1d": 86400,
    }.get(timeframe, 3600)
