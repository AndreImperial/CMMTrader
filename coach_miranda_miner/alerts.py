from __future__ import annotations

from .models import Candidate, TradeThesis, ValidationResult


class AlertFormatter:
    def format(
        self,
        candidate: Candidate,
        thesis: TradeThesis,
        validation: ValidationResult,
    ) -> str:
        targets = ", ".join(_price(target) for target in thesis.targets) or "n/a"
        evidence = "\n".join(f"- {item}" for item in thesis.evidence) or "- n/a"
        status = "APPROVED" if validation.approved else "NOT APPROVED"
        reasons = "\n".join(f"- {item}" for item in validation.reasons) or "- Passed"
        quality = _quality(thesis.confidence)
        market = []
        if candidate.volume_24h_usd is not None:
            market.append(f"24h volume: {_usd(candidate.volume_24h_usd)}")
        if candidate.open_interest_change_24h_pct is not None:
            market.append(f"OI 24h: {candidate.open_interest_change_24h_pct:.2f}%")
        market_text = " | ".join(market) or "Market context: n/a"
        return (
            f"Coach Miranda Miner\n"
            f"Symbol: {candidate.route_symbol} on {candidate.exchange_id}\n"
            f"Setup: {thesis.setup.value} | Signal: {thesis.signal.value} | "
            f"{status} | Grade: {quality}\n"
            f"Direction: {thesis.direction} | Confidence: {thesis.confidence:.2f}\n"
            f"{market_text}\n"
            f"Entry: {_price(thesis.entry)} | Stop: {_price(thesis.stop_loss)} | "
            f"Targets: {targets}\n"
            f"Risk/Reward: {thesis.risk_reward or 'n/a'}\n"
            f"Link: {candidate.trading_link or 'n/a'}\n\n"
            f"Evidence:\n{evidence}\n\n"
            f"Validation:\n{reasons}"
        )


def _quality(confidence: float) -> str:
    if confidence >= 0.8:
        return "A"
    if confidence >= 0.7:
        return "B"
    if confidence >= 0.6:
        return "C"
    return "D"


def _price(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}"


def _usd(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"
