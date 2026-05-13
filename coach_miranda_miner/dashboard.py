from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .coach import CoachMirandaMiner
    from .config import Settings
    from .models import Candidate, IntelligencePack, TradeThesis, ValidationResult
except ImportError:
    from coach_miranda_miner.coach import CoachMirandaMiner
    from coach_miranda_miner.config import Settings
    from coach_miranda_miner.models import (
        Candidate,
        IntelligencePack,
        TradeThesis,
        ValidationResult,
    )


DATA_MODES = {
    "Real candles: Coinbase public API": "coinbase",
    "Updating prices: CoinPaprika": "paprika",
    "Direct exchange APIs: Binance/Bybit/OKX (may be region-blocked)": "live",
    "CoinGecko free API": "coingecko",
    "Yahoo free API": "yahoo",
    "Offline demo": "fixture",
}

SIGNAL_PRIORITY = {"enter": 0, "watch": 1, "wait": 2, "reject": 3}


def main() -> None:
    st.set_page_config(
        page_title="Coach Miranda Miner",
        page_icon="CM",
        layout="wide",
    )
    st.title("Coach Miranda Miner")
    st.caption("Free-first crypto setup scanner. Alert/paper mode only.")

    base_settings = Settings.from_env()
    with st.sidebar:
        st.header("Controls")
        data_label = st.selectbox(
            "Data source",
            list(DATA_MODES.keys()),
            index=_mode_index(base_settings.data_mode),
        )
        discovery_limit = st.slider("Symbols to scan", 1, 10, base_settings.discovery_limit)
        candle_limit = st.slider("Candles per timeframe", 80, 300, base_settings.candle_limit)
        auto_refresh = st.checkbox("Auto refresh")
        refresh_seconds = st.selectbox("Refresh interval", [60, 180, 300, 900], index=1)
        run_scan = st.button("Scan Now", type="primary", use_container_width=True)
        show_history = st.checkbox("Show signal history", value=True)
        show_oi = st.checkbox("Show High OI + Volume", value=True)

        st.divider()
        st.write("Execution")
        st.warning("Live auto-trading is disabled. Use signals manually for now.")

    settings = replace(
        base_settings,
        data_mode=DATA_MODES[data_label],
        discovery_limit=discovery_limit,
        candle_limit=candle_limit,
        render_charts=False,
    )
    coach = CoachMirandaMiner(settings)

    status_cols = st.columns(4)
    status_cols[0].metric("Data Mode", settings.data_mode)
    status_cols[1].metric("Analyzer", settings.analyzer_mode)
    status_cols[2].metric("Trading Mode", settings.trading_mode)
    status_cols[3].metric("Telegram", "On" if coach.telegram.configured else "Off")
    st.caption(
        "Quality gates: "
        f"min confidence {settings.min_confidence:.0%}, "
        f"min R/R {settings.min_risk_reward:.1f}, "
        f"Telegram alerts at {settings.telegram_min_signal.upper()} or better."
    )
    if settings.data_mode == "coinbase":
        st.success("Using real public Coinbase OHLCV candles.")
    elif settings.data_mode == "paprika":
        st.warning("CoinPaprika mode has live prices but approximated intraday candles.")
    elif settings.data_mode == "live":
        st.warning("Direct exchange mode may be blocked by Render server location.")
    elif settings.data_mode == "fixture":
        st.warning("Offline demo mode uses synthetic candles.")

    if run_scan or auto_refresh:
        if show_oi:
            render_high_oi(coach)
        render_scan(coach)
    else:
        st.info("Press Scan Now to look for setups.")
        if show_oi:
            render_high_oi(coach)

    if show_history:
        render_history(coach)

    if auto_refresh:
        time.sleep(refresh_seconds)
        st.rerun()


def render_scan(coach: CoachMirandaMiner) -> None:
    try:
        market_regime = coach.gatekeeper.market_regime()
        candidates = coach.discovery.discover(coach.settings.discovery_limit)
    except Exception as exc:
        st.error("Live data is not available from this source right now.")
        st.code(str(exc))
        if coach.settings.data_mode == "live":
            st.info(
                "Binance/Bybit/OKX can block Render regions. "
                "Use the CoinPaprika source for hosted free prices."
            )
        return

    st.subheader("Market Regime")
    st.write(market_regime.reason)

    rows = []
    results: list[tuple[Candidate, IntelligencePack, TradeThesis, ValidationResult]] = []
    progress = st.progress(0)
    for index, candidate in enumerate(candidates, start=1):
        progress.progress(index / max(len(candidates), 1))
        passed, gate_reasons = coach.gatekeeper.filter_candidate(candidate)
        if not passed:
            rows.append(
                {
                    "symbol": candidate.route_symbol,
                    "exchange": candidate.exchange_id,
                    "setup": "blocked",
                    "signal": "skip",
                    "confidence": 0,
                    "status": "; ".join(gate_reasons),
                }
            )
            continue

        pack = coach.intelligence.gather(candidate, market_regime)
        thesis = coach.analyzer.analyze(pack)
        atr = next((item.atr for item in pack.indicators if item.timeframe == "15m"), None)
        validation = coach.validator.validate(thesis, market_regime, atr)
        message = coach.alerts.format(candidate, thesis, validation)
        coach.maybe_send_telegram_alert(candidate, thesis, validation, message)
        coach.journal.record_thesis(
            symbol=thesis.symbol,
            setup=thesis.setup.value,
            signal=thesis.signal.value,
            direction=thesis.direction,
            confidence=thesis.confidence,
            approved=validation.approved,
            payload_json=thesis.model_dump_json(),
            validation_json=validation.model_dump_json(),
        )
        results.append((candidate, pack, thesis, validation))
        rows.append(
            {
                "symbol": candidate.route_symbol,
                "source": candidate.exchange_id,
                "setup": thesis.setup.value,
                "signal": thesis.signal.value,
                "confidence": thesis.confidence,
                "entry": thesis.entry,
                "stop": thesis.stop_loss,
                "target_1": thesis.targets[0] if thesis.targets else None,
                "approved": validation.approved,
            }
        )
    progress.empty()

    rows = sorted(
        rows,
        key=lambda item: (
            SIGNAL_PRIORITY.get(item.get("signal", "reject"), 9),
            -float(item.get("confidence") or 0),
        ),
    )

    st.subheader("Signals")
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No candidates found.")

    for candidate, pack, thesis, validation in results:
        with st.expander(
            f"{candidate.route_symbol} - {thesis.setup.value} / {thesis.signal.value}",
            expanded=thesis.signal.value in {"watch", "enter"},
        ):
            left, right = st.columns([2, 1])
            with left:
                timeframe = st.selectbox(
                    "Chart timeframe",
                    list(pack.candles.keys()),
                    index=max(list(pack.candles.keys()).index("15m"), 0)
                    if "15m" in pack.candles
                    else 0,
                    key=f"tf-{candidate.route_symbol}",
                )
                st.plotly_chart(
                    _candlestick(pack, timeframe, thesis),
                    use_container_width=True,
                    key=f"chart-{candidate.route_symbol}-{timeframe}",
                )
            with right:
                st.metric("Signal", thesis.signal.value.upper())
                st.metric("Confidence", f"{thesis.confidence:.0%}")
                st.metric("Risk/Reward", thesis.risk_reward or "n/a")
                st.write("Entry", _fmt(thesis.entry))
                st.write("Stop", _fmt(thesis.stop_loss))
                st.write("Targets", ", ".join(_fmt(item) for item in thesis.targets) or "n/a")
                st.write("Validation")
                if validation.approved:
                    st.success("Approved")
                else:
                    for reason in validation.reasons:
                        st.warning(reason)
                st.write("Evidence")
                for item in thesis.evidence:
                    st.write(f"- {item}")
                if candidate.trading_link:
                    st.link_button("Open Trading Page", candidate.trading_link)


def render_high_oi(coach: CoachMirandaMiner) -> None:
    st.subheader("High OI + Volume")
    rows, warnings = coach.high_oi_watchlist()
    for warning in warnings[:3]:
        st.caption(warning)
    if not rows:
        st.info("No OI or volume rows available from the configured sources.")
        return

    frame = pd.DataFrame(
        [
            {
                "symbol": row.symbol,
                "source": row.source,
                "open_interest_usd": row.open_interest_usd,
                "volume_24h_usd": row.volume_24h_usd,
                "score": row.score,
                "price": row.price,
                "status": row.status,
                "updated": row.updated_at.isoformat(timespec="minutes"),
            }
            for row in rows
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "open_interest_usd": st.column_config.NumberColumn("OI USD", format="$%.0f"),
            "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
            "score": st.column_config.NumberColumn("OI/Vol Score", format="%.0f"),
            "price": st.column_config.NumberColumn("Price", format="$%.4f"),
        },
    )


def render_history(coach: CoachMirandaMiner) -> None:
    st.subheader("Recent Signal History")
    rows = coach.journal.recent_theses(20)
    if not rows:
        st.caption("No saved signals yet.")
        return
    frame = pd.DataFrame(
        [
            {
                "time": row["created_at"],
                "symbol": row["symbol"],
                "setup": row["setup"],
                "signal": row["signal"],
                "confidence": row["confidence"],
                "approved": row["approved"],
            }
            for row in rows
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _candlestick(pack: IntelligencePack, timeframe: str, thesis: TradeThesis) -> go.Figure:
    candles = pack.candles[timeframe]
    frame = pd.DataFrame([item.model_dump() for item in candles])
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["timestamp"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name=timeframe,
        )
    )
    fig.add_trace(
        go.Bar(
            x=frame["timestamp"],
            y=frame["volume"],
            name="Volume",
            marker_color="rgba(120, 160, 220, 0.35)",
            yaxis="y2",
        )
    )
    for value, color, label in [
        (thesis.entry, "#3b82f6", "Entry"),
        (thesis.stop_loss, "#ef4444", "Stop"),
    ]:
        if value is not None:
            fig.add_hline(y=value, line_color=color, line_dash="dash", annotation_text=label)
    for index, target in enumerate(thesis.targets, start=1):
        fig.add_hline(
            y=target,
            line_color="#22c55e",
            line_dash="dot",
            annotation_text=f"Target {index}",
        )
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{pack.candidate.route_symbol} {timeframe}",
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            visible=False,
        ),
    )
    return fig


def _mode_index(mode: str) -> int:
    values = list(DATA_MODES.values())
    return values.index(mode) if mode in values else 0


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}"


if __name__ == "__main__":
    main()
