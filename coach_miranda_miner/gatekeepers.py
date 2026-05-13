from __future__ import annotations

from .exchanges import ExchangeRouter
from .models import Candidate, MarketRegime


class Gatekeeper:
    def __init__(
        self,
        router: ExchangeRouter,
        btc_kill_switch_drop_pct: float,
        min_volume_24h_usd: float,
    ) -> None:
        self.router = router
        self.btc_kill_switch_drop_pct = abs(btc_kill_switch_drop_pct)
        self.min_volume_24h_usd = min_volume_24h_usd

    def market_regime(self) -> MarketRegime:
        route = self.router.first_available_route("BTC", "USDT")
        if route is None:
            raise ValueError("No BTC/USDT route available for market regime check.")
        exchange_id, symbol = route
        ticker = self.router.fetch_ticker(exchange_id, symbol)
        change = float(ticker.percentage or 0.0)
        if change <= -self.btc_kill_switch_drop_pct:
            return MarketRegime(
                btc_change_24h_pct=change,
                longs_allowed=False,
                reason=f"BTC is down {change:.2f}% in 24h; long analysis halted.",
            )
        return MarketRegime(
            btc_change_24h_pct=change,
            longs_allowed=True,
            reason=f"BTC regime acceptable at {change:.2f}% in 24h.",
        )

    def filter_candidate(self, candidate: Candidate) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        ticker = self.router.fetch_ticker(candidate.exchange_id, candidate.route_symbol)
        if ticker.quote_volume is not None and ticker.quote_volume < self.min_volume_24h_usd:
            reasons.append(
                f"24h quote volume {ticker.quote_volume:.0f} below "
                f"{self.min_volume_24h_usd:.0f}."
            )
        return len(reasons) == 0, reasons
