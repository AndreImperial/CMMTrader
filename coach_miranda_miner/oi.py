from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import requests


DEFAULT_OI_BASES = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"]


@dataclass(frozen=True)
class OISnapshot:
    symbol: str
    source: str
    open_interest: float | None
    open_interest_usd: float | None
    volume_24h_usd: float | None
    price: float | None
    status: str
    updated_at: datetime

    @property
    def score(self) -> float:
        oi = self.open_interest_usd or 0.0
        volume = self.volume_24h_usd or 0.0
        return oi + (volume * 0.35)


class OpenInterestScanner:
    def __init__(self, price_router, bases: list[str] | None = None) -> None:
        self.price_router = price_router
        self.bases = bases or DEFAULT_OI_BASES
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CMMTrader"})

    def scan(self) -> tuple[list[OISnapshot], list[str]]:
        warnings: list[str] = []
        snapshots = self._scan_okx(warnings)
        if snapshots:
            return self._merge_volume(snapshots), warnings

        snapshots = self._scan_binance(warnings)
        snapshots.extend(self._scan_bybit(warnings))
        if not snapshots:
            warnings.append(
                "No public derivatives OI endpoint was reachable from this server. "
                "This can happen on hosted regions blocked by exchanges."
            )
            return self._volume_only_fallback(), warnings
        return self._merge_volume(snapshots), warnings

    def _scan_okx(self, warnings: list[str]) -> list[OISnapshot]:
        try:
            response = self.session.get(
                "https://www.okx.com/api/v5/public/open-interest",
                params={"instType": "SWAP"},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            warnings.append(f"OKX OI unavailable: {exc}")
            return []

        wanted = {f"{base}-USDT-SWAP": base for base in self.bases}
        rows: list[OISnapshot] = []
        for item in payload.get("data", []):
            inst_id = item.get("instId")
            if inst_id not in wanted:
                continue
            symbol = f"{wanted[inst_id]}/USD"
            oi_usd = _float_or_none(item.get("oiUsd"))
            rows.append(
                OISnapshot(
                    symbol=symbol,
                    source="OKX",
                    open_interest=_float_or_none(item.get("oi")),
                    open_interest_usd=oi_usd,
                    volume_24h_usd=None,
                    price=None,
                    status="OI live",
                    updated_at=_timestamp_ms(item.get("ts")),
                )
            )
        return rows

    def _scan_binance(self, warnings: list[str]) -> list[OISnapshot]:
        rows = []
        for base in self.bases:
            try:
                response = self.session.get(
                    "https://fapi.binance.com/fapi/v1/openInterest",
                    params={"symbol": f"{base}USDT"},
                    timeout=12,
                )
                response.raise_for_status()
                payload = response.json()
                price, volume = self._price_and_volume(base)
                oi = _float_or_none(payload.get("openInterest"))
                rows.append(
                    OISnapshot(
                        symbol=f"{base}/USD",
                        source="Binance Futures",
                        open_interest=oi,
                        open_interest_usd=oi * price if oi is not None and price is not None else None,
                        volume_24h_usd=volume,
                        price=price,
                        status="OI live",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            except Exception as exc:
                warnings.append(f"Binance OI unavailable for {base}: {exc}")
        return rows

    def _scan_bybit(self, warnings: list[str]) -> list[OISnapshot]:
        rows = []
        for base in self.bases:
            try:
                response = self.session.get(
                    "https://api.bybit.com/v5/market/open-interest",
                    params={
                        "category": "linear",
                        "symbol": f"{base}USDT",
                        "intervalTime": "1h",
                        "limit": 1,
                    },
                    timeout=12,
                )
                response.raise_for_status()
                payload = response.json()
                items = payload.get("result", {}).get("list", [])
                if not items:
                    continue
                price, volume = self._price_and_volume(base)
                oi = _float_or_none(items[0].get("openInterest"))
                rows.append(
                    OISnapshot(
                        symbol=f"{base}/USD",
                        source="Bybit",
                        open_interest=oi,
                        open_interest_usd=oi * price if oi is not None and price is not None else None,
                        volume_24h_usd=volume,
                        price=price,
                        status="OI live",
                        updated_at=_timestamp_ms(items[0].get("timestamp")),
                    )
                )
            except Exception as exc:
                warnings.append(f"Bybit OI unavailable for {base}: {exc}")
        return rows

    def _merge_volume(self, snapshots: list[OISnapshot]) -> list[OISnapshot]:
        enriched = []
        for snapshot in snapshots:
            base = snapshot.symbol.split("/")[0]
            price, volume = self._price_and_volume(base)
            enriched.append(
                OISnapshot(
                    symbol=snapshot.symbol,
                    source=snapshot.source,
                    open_interest=snapshot.open_interest,
                    open_interest_usd=snapshot.open_interest_usd,
                    volume_24h_usd=snapshot.volume_24h_usd or volume,
                    price=snapshot.price or price,
                    status=snapshot.status,
                    updated_at=snapshot.updated_at,
                )
            )
        return sorted(enriched, key=lambda item: item.score, reverse=True)

    def _volume_only_fallback(self) -> list[OISnapshot]:
        rows = []
        for base in self.bases:
            price, volume = self._price_and_volume(base)
            if price is None and volume is None:
                continue
            rows.append(
                OISnapshot(
                    symbol=f"{base}/USD",
                    source="Coinbase",
                    open_interest=None,
                    open_interest_usd=None,
                    volume_24h_usd=volume,
                    price=price,
                    status="Volume only; OI unavailable",
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return sorted(rows, key=lambda item: item.volume_24h_usd or 0.0, reverse=True)

    def _price_and_volume(self, base: str) -> tuple[float | None, float | None]:
        try:
            ticker = self.price_router.fetch_ticker("coinbase", f"{base}/USD")
            return ticker.last, ticker.quote_volume
        except Exception:
            return None, None


def _float_or_none(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp_ms(value) -> datetime:
    number = _float_or_none(value)
    if number is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(number / 1000, timezone.utc)

