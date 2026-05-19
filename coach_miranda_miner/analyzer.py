from __future__ import annotations

import base64
import json
from pathlib import Path

from .models import CandleSnapshot, IntelligencePack, Setup, SignalState, TradeThesis
from .prompts import MIRANDA_SYSTEM_PROMPT


class Analyzer:
    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        raise NotImplementedError


class RuleBasedAnalyzer(Analyzer):
    """Free deterministic Miranda analyzer using candles and indicators."""

    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        by_timeframe = {item.timeframe: item for item in pack.indicators}
        tf_15m = by_timeframe.get("15m") or pack.indicators[-1]
        tf_1h = by_timeframe.get("1h") or pack.indicators[-1]
        tf_4h = by_timeframe.get("4h") or tf_1h
        candles_15m = pack.candles.get("15m", [])
        candles_1h = pack.candles.get("1h", [])

        if not pack.market_regime.longs_allowed and not pack.market_regime.shorts_allowed:
            return TradeThesis(
                symbol=pack.candidate.route_symbol,
                setup=Setup.NONE,
                signal=SignalState.REJECT,
                direction="none",
                confidence=0.0,
                invalidation_reason=pack.market_regime.reason,
                evidence=[pack.market_regime.reason],
            )

        prison = _prison_break_state(candles_15m)
        short_prison = _short_prison_break_state(candles_15m)
        volume_confirmed = (tf_15m.relative_volume or 0.0) >= 1.25
        compression = _compression_ratio(candles_15m)
        support = _support_zone(candles_1h or candles_15m)
        resistance = _resistance_zone(candles_1h or candles_15m)
        macd_bullish = (
            tf_1h.macd is not None
            and tf_1h.macd_signal is not None
            and tf_1h.macd > tf_1h.macd_signal
        )
        macd_bearish = (
            tf_1h.macd is not None
            and tf_1h.macd_signal is not None
            and tf_1h.macd < tf_1h.macd_signal
        )
        rsi_ok = tf_15m.rsi is not None and 35 <= tf_15m.rsi <= 68
        short_rsi_ok = tf_15m.rsi is not None and 32 <= tf_15m.rsi <= 65

        if pack.market_regime.longs_allowed and _transition_play(tf_15m, tf_1h):
            return _long_thesis(
                pack,
                Setup.TRANSITION_PLAY,
                prison,
                confidence=_confidence(0.58, prison, volume_confirmed, compression, macd_bullish),
                evidence=[
                    "RSI is recovering from a weak zone.",
                    "1h MACD momentum supports reversal conditions.",
                    f"15m prison-break state is {prison.value}.",
                ],
            )

        if (
            pack.market_regime.shorts_allowed
            and _short_transition_play(tf_15m, tf_1h)
        ):
            return _short_thesis(
                pack,
                Setup.TRANSITION_PLAY,
                short_prison,
                confidence=_confidence(0.58, short_prison, volume_confirmed, compression, macd_bearish),
                evidence=[
                    "RSI is rolling over from a strong zone.",
                    "1h MACD momentum supports bearish reversal conditions.",
                    f"15m short prison-break state is {short_prison.value}.",
                ],
            )

        if pack.market_regime.longs_allowed and support and _is_bounce(candles_15m, support) and rsi_ok:
            return _long_thesis(
                pack,
                Setup.BOUNCE,
                prison,
                confidence=_confidence(0.58, prison, volume_confirmed, compression, macd_bullish),
                evidence=[
                    f"Support zone has {support['touches']} wick touches.",
                    "Latest candles show rejection near support.",
                    f"15m RSI is {tf_15m.rsi:.2f}.",
                ],
            )

        if (
            pack.market_regime.shorts_allowed
            and resistance
            and _is_resistance_rejection(candles_15m, resistance)
            and short_rsi_ok
        ):
            return _short_thesis(
                pack,
                Setup.BOUNCE,
                short_prison,
                confidence=_confidence(0.58, short_prison, volume_confirmed, compression, macd_bearish),
                evidence=[
                    f"Resistance zone has {resistance['touches']} wick touches.",
                    "Latest candles show rejection near resistance.",
                    f"15m RSI is {tf_15m.rsi:.2f}.",
                ],
            )

        if (
            pack.market_regime.longs_allowed
            and compression < 0.7
            and prison in {SignalState.WATCH, SignalState.ENTER}
        ):
            evidence = [
                f"15m range compression ratio is {compression:.2f}.",
                f"15m prison-break state is {prison.value}.",
            ]
            if volume_confirmed:
                evidence.append("Relative volume confirms breakout.")
            else:
                evidence.append("Volume confirmation is not strong enough for ENTER.")
            return _long_thesis(
                pack,
                Setup.APEX_SQUEEZE,
                prison if volume_confirmed else SignalState.WATCH,
                confidence=_confidence(0.62, prison, volume_confirmed, compression, macd_bullish),
                evidence=evidence,
            )

        if (
            pack.market_regime.shorts_allowed
            and compression < 0.7
            and short_prison in {SignalState.WATCH, SignalState.ENTER}
        ):
            evidence = [
                f"15m range compression ratio is {compression:.2f}.",
                f"15m short prison-break state is {short_prison.value}.",
            ]
            if volume_confirmed:
                evidence.append("Relative volume confirms bearish breakdown.")
            else:
                evidence.append("Volume confirmation is not strong enough for ENTER.")
            return _short_thesis(
                pack,
                Setup.APEX_SQUEEZE,
                short_prison if volume_confirmed else SignalState.WATCH,
                confidence=_confidence(0.62, short_prison, volume_confirmed, compression, macd_bearish),
                evidence=evidence,
            )

        if (
            pack.market_regime.longs_allowed
            and rsi_ok
            and macd_bullish
            and (tf_4h.rsi is None or tf_4h.rsi < 72)
            and resistance is not None
        ):
            return _long_thesis(
                pack,
                Setup.TABO,
                prison,
                confidence=_confidence(0.56, prison, volume_confirmed, compression, macd_bullish),
                evidence=[
                    "1h MACD is above signal.",
                    "15m RSI is in a tradable continuation range.",
                    f"Nearby resistance zone has {resistance['touches']} wick touches.",
                    f"15m prison-break state is {prison.value}.",
                ],
            )

        if (
            pack.market_regime.shorts_allowed
            and short_rsi_ok
            and macd_bearish
            and (tf_4h.rsi is None or tf_4h.rsi > 28)
            and support is not None
        ):
            return _short_thesis(
                pack,
                Setup.TABO,
                short_prison,
                confidence=_confidence(0.56, short_prison, volume_confirmed, compression, macd_bearish),
                evidence=[
                    "1h MACD is below signal.",
                    "15m RSI is in a tradable bearish continuation range.",
                    f"Nearby support zone has {support['touches']} wick touches.",
                    f"15m short prison-break state is {short_prison.value}.",
                ],
            )

        return TradeThesis(
            symbol=pack.candidate.route_symbol,
            setup=Setup.NONE,
            signal=SignalState.WAIT,
            direction="none",
            confidence=0.35,
            invalidation_reason="No deterministic setup passed the current filters.",
            evidence=["Momentum and entry timing are not aligned."],
        )


class OpenAIVisionAnalyzer(Analyzer):
    def __init__(self, model: str) -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model

    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        response = self.client.responses.create(
            model=self.model,
            instructions=MIRANDA_SYSTEM_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": self._content(pack),
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "trade_thesis",
                    "schema": _strict_schema(),
                    "strict": True,
                }
            },
        )
        return TradeThesis.model_validate_json(response.output_text)

    def _content(self, pack: IntelligencePack) -> list[dict]:
        content: list[dict] = [
            {
                "type": "input_text",
                "text": json.dumps(
                    {
                        "candidate": pack.candidate.model_dump(),
                        "market_regime": pack.market_regime.model_dump(),
                        "indicators": [item.model_dump() for item in pack.indicators],
                        "news_summary": pack.news_summary,
                    },
                    default=str,
                ),
            }
        ]
        for chart_path in pack.chart_paths:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _image_data_url(chart_path),
                }
            )
        return content


def _image_data_url(path: str) -> str:
    raw = Path(path).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _strict_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "symbol",
            "setup",
            "signal",
            "direction",
            "confidence",
            "entry",
            "stop_loss",
            "targets",
            "risk_reward",
            "invalidation_reason",
            "evidence",
            "news_veto",
        ],
        "properties": {
            "symbol": {"type": "string"},
            "setup": {
                "type": "string",
                "enum": ["bounce", "apex_squeeze", "transition_play", "tabo", "none"],
            },
            "signal": {
                "type": "string",
                "enum": ["wait", "watch", "enter", "reject"],
            },
            "direction": {"type": "string", "enum": ["long", "short", "none"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "entry": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "stop_loss": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "targets": {"type": "array", "items": {"type": "number"}},
            "risk_reward": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "invalidation_reason": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
            "news_veto": {"type": "boolean"},
        },
    }


def _long_thesis(
    pack: IntelligencePack,
    setup: Setup,
    signal: SignalState,
    confidence: float,
    evidence: list[str],
) -> TradeThesis:
    tf_15m = {item.timeframe: item for item in pack.indicators}.get("15m") or pack.indicators[-1]
    entry = tf_15m.close
    stop_distance = tf_15m.atr or entry * 0.015
    stop = entry - stop_distance
    targets = [entry + (stop_distance * 1.5), entry + (stop_distance * 2.5)]
    risk_reward = (targets[-1] - entry) / stop_distance if stop_distance > 0 else None
    if signal == SignalState.WAIT:
        evidence.append("Price remains inside consolidation; waiting avoids fakeouts.")
    if signal == SignalState.WATCH:
        evidence.append("Breakout needs follow-through or retest confirmation before entry.")
    if signal == SignalState.ENTER:
        evidence.append("15m confirmation candle closed outside the prison range.")
    evidence.append(f"ATR stop distance is {stop_distance:.6g}.")
    return TradeThesis(
        symbol=pack.candidate.route_symbol,
        setup=setup,
        signal=signal,
        direction="long",
        confidence=confidence,
        entry=entry,
        stop_loss=stop,
        targets=targets,
        risk_reward=risk_reward,
        evidence=evidence,
    )


def _short_thesis(
    pack: IntelligencePack,
    setup: Setup,
    signal: SignalState,
    confidence: float,
    evidence: list[str],
) -> TradeThesis:
    tf_15m = {item.timeframe: item for item in pack.indicators}.get("15m") or pack.indicators[-1]
    entry = tf_15m.close
    stop_distance = tf_15m.atr or entry * 0.015
    stop = entry + stop_distance
    targets = [entry - (stop_distance * 1.5), entry - (stop_distance * 2.5)]
    risk_reward = (entry - targets[-1]) / stop_distance if stop_distance > 0 else None
    if signal == SignalState.WAIT:
        evidence.append("Price remains inside consolidation; waiting avoids fake breakdowns.")
    if signal == SignalState.WATCH:
        evidence.append("Bearish break needs follow-through or retest confirmation before entry.")
    if signal == SignalState.ENTER:
        evidence.append("15m confirmation candle closed below the prison range.")
    evidence.append(f"ATR stop distance is {stop_distance:.6g}.")
    return TradeThesis(
        symbol=pack.candidate.route_symbol,
        setup=setup,
        signal=signal,
        direction="short",
        confidence=confidence,
        entry=entry,
        stop_loss=stop,
        targets=[target for target in targets if target > 0],
        risk_reward=risk_reward,
        evidence=evidence,
    )


def _prison_break_state(candles: list[CandleSnapshot]) -> SignalState:
    if len(candles) < 24:
        return SignalState.WAIT
    prison = candles[-23:-3]
    last_three = candles[-3:]
    high = max(candle.high for candle in prison)
    low = min(candle.low for candle in prison)
    prev_close = last_three[-2].close
    last_close = last_three[-1].close

    if low <= last_close <= high:
        if prev_close > high or prev_close < low:
            return SignalState.REJECT
        return SignalState.WAIT
    if last_close > high:
        return SignalState.ENTER if prev_close > high else SignalState.WATCH
    if last_close < low:
        return SignalState.REJECT
    return SignalState.WAIT


def _short_prison_break_state(candles: list[CandleSnapshot]) -> SignalState:
    if len(candles) < 24:
        return SignalState.WAIT
    prison = candles[-23:-3]
    last_three = candles[-3:]
    high = max(candle.high for candle in prison)
    low = min(candle.low for candle in prison)
    prev_close = last_three[-2].close
    last_close = last_three[-1].close

    if low <= last_close <= high:
        if prev_close > high or prev_close < low:
            return SignalState.REJECT
        return SignalState.WAIT
    if last_close < low:
        return SignalState.ENTER if prev_close < low else SignalState.WATCH
    if last_close > high:
        return SignalState.REJECT
    return SignalState.WAIT


def _compression_ratio(candles: list[CandleSnapshot]) -> float:
    if len(candles) < 40:
        return 1.0
    prior = candles[-40:-20]
    recent = candles[-20:]
    prior_range = max(item.high for item in prior) - min(item.low for item in prior)
    recent_range = max(item.high for item in recent) - min(item.low for item in recent)
    if prior_range <= 0:
        return 1.0
    return recent_range / prior_range


def _support_zone(candles: list[CandleSnapshot]) -> dict | None:
    if len(candles) < 20:
        return None
    lows = [candle.low for candle in candles[-50:]]
    support = min(lows)
    tolerance = support * 0.006
    touches = sum(1 for low in lows if abs(low - support) <= tolerance)
    if touches < 3:
        return None
    return {"price": support, "touches": touches}


def _resistance_zone(candles: list[CandleSnapshot]) -> dict | None:
    if len(candles) < 20:
        return None
    highs = [candle.high for candle in candles[-50:]]
    resistance = max(highs)
    tolerance = resistance * 0.006
    touches = sum(1 for high in highs if abs(high - resistance) <= tolerance)
    if touches < 3:
        return None
    return {"price": resistance, "touches": touches}


def _is_bounce(candles: list[CandleSnapshot], support: dict) -> bool:
    if len(candles) < 3:
        return False
    latest = candles[-1]
    prior = candles[-2]
    support_price = support["price"]
    near_support = min(latest.low, prior.low) <= support_price * 1.012
    bullish_rejection = latest.close > latest.open and latest.close > prior.close
    lower_wick = min(latest.open, latest.close) - latest.low
    body = abs(latest.close - latest.open) or latest.close * 0.0001
    return near_support and bullish_rejection and lower_wick >= body * 0.5


def _is_resistance_rejection(candles: list[CandleSnapshot], resistance: dict) -> bool:
    if len(candles) < 3:
        return False
    latest = candles[-1]
    prior = candles[-2]
    resistance_price = resistance["price"]
    near_resistance = max(latest.high, prior.high) >= resistance_price * 0.988
    bearish_rejection = latest.close < latest.open and latest.close < prior.close
    upper_wick = latest.high - max(latest.open, latest.close)
    body = abs(latest.close - latest.open) or latest.close * 0.0001
    return near_resistance and bearish_rejection and upper_wick >= body * 0.5


def _transition_play(tf_15m, tf_1h) -> bool:
    if tf_15m.rsi is None or tf_1h.macd is None or tf_1h.macd_signal is None:
        return False
    return 35 <= tf_15m.rsi <= 48 and tf_1h.macd > tf_1h.macd_signal


def _short_transition_play(tf_15m, tf_1h) -> bool:
    if tf_15m.rsi is None or tf_1h.macd is None or tf_1h.macd_signal is None:
        return False
    return 55 <= tf_15m.rsi <= 70 and tf_1h.macd < tf_1h.macd_signal


def _confidence(
    base: float,
    prison: SignalState,
    volume_confirmed: bool,
    compression: float,
    macd_bullish: bool,
) -> float:
    score = base
    if prison == SignalState.WATCH:
        score += 0.04
    if prison == SignalState.ENTER:
        score += 0.12
    if volume_confirmed:
        score += 0.08
    if compression < 0.7:
        score += 0.05
    if macd_bullish:
        score += 0.04
    if prison == SignalState.REJECT:
        score -= 0.18
    return max(0.0, min(score, 0.92))
