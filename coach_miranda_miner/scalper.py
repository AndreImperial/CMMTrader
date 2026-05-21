from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import alma, atr, cci, ema, relative_volume
from .models import Candidate, Setup, SetupScore, SignalState, TradeThesis, ValidationResult
from .validator import ThesisValidator


@dataclass(frozen=True)
class ScalpScanResult:
    candidate: Candidate
    score: SetupScore
    candles: dict[str, pd.DataFrame]
    thesis: TradeThesis
    validation: ValidationResult
    alert_sent: bool = False


class AlmaCciScalper:
    def __init__(
        self,
        validator: ThesisValidator,
        alma_length: int = 20,
        alma_offset: float = 0.8,
        alma_sigma: float = 8.0,
        ema_length: int = 9,
        cci_length: int = 20,
        target_r_multiple: float = 2.0,
    ) -> None:
        self.validator = validator
        self.alma_length = alma_length
        self.alma_offset = alma_offset
        self.alma_sigma = alma_sigma
        self.ema_length = ema_length
        self.cci_length = cci_length
        self.target_r_multiple = target_r_multiple

    def analyze(
        self,
        candidate: Candidate,
        candles: dict[str, pd.DataFrame],
        rank: int,
        market_regime,
    ) -> ScalpScanResult:
        enriched = {timeframe: self._with_indicators(frame) for timeframe, frame in candles.items()}
        thesis = self._thesis(candidate, enriched, market_regime)
        execution_atr = _last_float(atr(enriched["3m"], 14))
        validation = self.validator.validate(thesis, market_regime, execution_atr)
        score = _scalp_score(candidate, rank, thesis, enriched)
        return ScalpScanResult(
            candidate=candidate,
            score=score,
            candles=enriched,
            thesis=thesis,
            validation=validation,
        )

    def _with_indicators(self, candles: pd.DataFrame) -> pd.DataFrame:
        frame = candles.copy()
        frame["ema_9"] = ema(frame["close"], self.ema_length)
        frame["alma_20"] = alma(frame["close"], self.alma_length, self.alma_offset, self.alma_sigma)
        frame["cci_20"] = cci(frame, self.cci_length)
        frame["relative_volume"] = relative_volume(frame["volume"], 20)
        return frame

    def _thesis(self, candidate: Candidate, candles: dict[str, pd.DataFrame], market_regime) -> TradeThesis:
        required = ("15m", "5m", "3m")
        if any(timeframe not in candles or len(candles[timeframe]) < self.cci_length for timeframe in required):
            return TradeThesis(
                symbol=candidate.route_symbol,
                setup=Setup.ALMA_CCI_SCALP,
                signal=SignalState.WAIT,
                direction="none",
                confidence=0.0,
                invalidation_reason="Not enough candles for CCI 20 scalp confirmation.",
                evidence=["Needs 15m, 5m, and 3m candles with at least 20 bars."],
            )

        bias = _bias(candles["15m"])
        long_structure = _aligned_long(candles["5m"])
        short_structure = _aligned_short(candles["5m"])
        execution = candles["3m"]
        last = execution.iloc[-1]
        rel_vol = _last_float(execution["relative_volume"]) or 0.0

        long_cross = _crossed_above(execution["ema_9"], execution["alma_20"])
        short_cross = _crossed_below(execution["ema_9"], execution["alma_20"])
        long_cci_cross = _cci_rising_from_lower_zone(execution["cci_20"])
        short_cci_cross = _cci_falling_from_upper_zone(execution["cci_20"])
        long_ready = bias == "long" and long_structure and _aligned_long(execution)
        short_ready = bias == "short" and short_structure and _aligned_short(execution)

        if long_ready and long_cross and long_cci_cross and market_regime.longs_allowed:
            return self._build_trade(candidate, execution, "long", SignalState.ENTER, rel_vol, long_cross, long_cci_cross)
        if short_ready and short_cross and short_cci_cross and market_regime.shorts_allowed:
            return self._build_trade(
                candidate,
                execution,
                "short",
                SignalState.ENTER,
                rel_vol,
                short_cross,
                short_cci_cross,
            )
        if bias == "long" and long_structure and _aligned_long(execution):
            return self._build_trade(candidate, execution, "long", SignalState.WATCH, rel_vol, long_cross, long_cci_cross)
        if bias == "short" and short_structure and _aligned_short(execution):
            return self._build_trade(
                candidate,
                execution,
                "short",
                SignalState.WATCH,
                rel_vol,
                short_cross,
                short_cci_cross,
            )

        return TradeThesis(
            symbol=candidate.route_symbol,
            setup=Setup.ALMA_CCI_SCALP,
            signal=SignalState.WAIT,
            direction="none",
            confidence=0.25,
            invalidation_reason="No aligned scalp bias/structure/execution stack.",
            evidence=[
                f"15m bias: {bias}",
                f"5m long structure: {long_structure}",
                f"5m short structure: {short_structure}",
                "3m execution has not aligned with ALMA/EMA plus CCI trigger.",
            ],
        )

    def _build_trade(
        self,
        candidate: Candidate,
        execution: pd.DataFrame,
        direction: str,
        signal: SignalState,
        rel_vol: float,
        alma_cross: bool,
        cci_cross: bool,
    ) -> TradeThesis:
        latest = execution.iloc[-1]
        entry = float(latest["close"])
        atr_value = _last_float(atr(execution, 14)) or max(entry * 0.003, 0.000001)
        recent = execution.tail(12)
        if direction == "long":
            swing_stop = float(recent["low"].min())
            stop = min(swing_stop, entry - atr_value)
            risk = max(entry - stop, atr_value * 0.5)
            stop = entry - risk
            target = entry + risk * self.target_r_multiple
        else:
            swing_stop = float(recent["high"].max())
            stop = max(swing_stop, entry + atr_value)
            risk = max(stop - entry, atr_value * 0.5)
            stop = entry + risk
            target = entry - risk * self.target_r_multiple
        confidence = 0.58
        if signal == SignalState.ENTER:
            confidence += 0.14
        if rel_vol >= 1.3:
            confidence += 0.08
        if alma_cross:
            confidence += 0.06
        if cci_cross:
            confidence += 0.06
        confidence = min(confidence, 0.88)
        trigger_text = "confirmed" if signal == SignalState.ENTER else "forming"
        return TradeThesis(
            symbol=candidate.route_symbol,
            setup=Setup.ALMA_CCI_SCALP,
            signal=signal,
            direction=direction,
            confidence=confidence,
            entry=entry,
            stop_loss=stop,
            targets=[target],
            risk_reward=self.target_r_multiple,
            evidence=[
                f"15m bias, 5m structure, and 3m execution are stacked {direction}.",
                f"3m EMA9 / ALMA(20, 0.8, 8) trigger is {trigger_text}.",
                f"CCI 20 momentum trigger is {trigger_text} from the -100/+100 zone; rel volume {rel_vol:.2f}x.",
                "Scalp model uses 15m bias, 5m structure, 3m execution.",
            ],
        )


def _scalp_score(
    candidate: Candidate,
    rank: int,
    thesis: TradeThesis,
    candles: dict[str, pd.DataFrame],
) -> SetupScore:
    rel_vol = _last_float(candles["3m"]["relative_volume"])
    cci_value = _last_float(candles["3m"]["cci_20"])
    score = thesis.confidence * 70
    if thesis.signal == SignalState.ENTER:
        score += 15
    if rel_vol is not None:
        score += min(max((rel_vol - 1.0) * 10, 0), 15)
    reasons = [
        f"Scalp signal: {thesis.signal.value.upper()} {thesis.direction.upper()}",
        "ALMA 20 / EMA9 plus CCI 20 stack.",
    ]
    if rel_vol is not None:
        reasons.append(f"3m relative volume {rel_vol:.2f}x.")
    if cci_value is not None:
        reasons.append(f"3m CCI 20 is {cci_value:.1f}.")
    return SetupScore(
        symbol=candidate.route_symbol,
        rank=rank,
        score=score,
        volume_24h_usd=candidate.volume_24h_usd,
        price_change_24h_pct=None,
        oi_change_24h_pct=candidate.open_interest_change_24h_pct,
        relative_volume=rel_vol,
        btc_regime_ok=True,
        prefilter_reasons=reasons,
    )


def _bias(candles: pd.DataFrame) -> str:
    if _aligned_long(candles) and (_last_float(candles["cci_20"]) or 0) > 0:
        return "long"
    if _aligned_short(candles) and (_last_float(candles["cci_20"]) or 0) < 0:
        return "short"
    return "neutral"


def _aligned_long(candles: pd.DataFrame) -> bool:
    latest = candles.iloc[-1]
    return _valid(latest["alma_20"], latest["ema_9"], latest["cci_20"]) and (
        latest["ema_9"] > latest["alma_20"] and latest["cci_20"] > -100
    )


def _aligned_short(candles: pd.DataFrame) -> bool:
    latest = candles.iloc[-1]
    return _valid(latest["alma_20"], latest["ema_9"], latest["cci_20"]) and (
        latest["ema_9"] < latest["alma_20"] and latest["cci_20"] < 100
    )


def _crossed_above(left: pd.Series, right: pd.Series) -> bool:
    return _valid_pair(left, right) and left.iloc[-2] <= right.iloc[-2] and left.iloc[-1] > right.iloc[-1]


def _crossed_below(left: pd.Series, right: pd.Series) -> bool:
    return _valid_pair(left, right) and left.iloc[-2] >= right.iloc[-2] and left.iloc[-1] < right.iloc[-1]


def _cci_rising_from_lower_zone(series: pd.Series) -> bool:
    if not _valid(series.iloc[-2], series.iloc[-1]):
        return False
    previous = float(series.iloc[-2])
    current = float(series.iloc[-1])
    return current > previous and previous <= -100 and current > -100


def _cci_falling_from_upper_zone(series: pd.Series) -> bool:
    if not _valid(series.iloc[-2], series.iloc[-1]):
        return False
    previous = float(series.iloc[-2])
    current = float(series.iloc[-1])
    return current < previous and previous >= 100 and current < 100


def _valid_pair(left: pd.Series, right: pd.Series) -> bool:
    return _valid(left.iloc[-2], left.iloc[-1], right.iloc[-2], right.iloc[-1])


def _valid(*values) -> bool:
    return all(value is not None and not pd.isna(value) for value in values)


def _last_float(series: pd.Series) -> float | None:
    value = series.iloc[-1]
    if value is None or pd.isna(value):
        return None
    return float(value)
