from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .alerts import alert_grade
    from .coach import CoachMirandaMiner
    from .config import Settings
    from .models import IntelligencePack, TradeThesis
except ImportError:
    from coach_miranda_miner.alerts import alert_grade
    from coach_miranda_miner.coach import CoachMirandaMiner
    from coach_miranda_miner.config import Settings
    from coach_miranda_miner.models import (
        IntelligencePack,
        TradeThesis,
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
TRADINGVIEW_HEIGHT = 760


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
        discovery_limit = st.slider("Top universe", 1, 100, min(base_settings.prefilter_limit, 100))
        deep_scan_limit = st.slider("Deep analysis limit", 1, 30, min(base_settings.deep_scan_limit, 30))
        candle_limit = st.slider("Candles per timeframe", 80, 300, base_settings.candle_limit)
        auto_refresh = st.checkbox("Auto scan", value=base_settings.auto_scan_enabled)
        refresh_seconds = st.selectbox(
            "Refresh interval",
            [60, 180, 300, 900],
            index=_refresh_index(base_settings.auto_scan_interval_seconds),
        )
        run_scan = st.button("Scan Now", type="primary", use_container_width=True)
        clear_cache = st.button("Clear Scan Cache", use_container_width=True)
        show_history = st.checkbox("Show signal history", value=True)
        show_oi = st.checkbox("Show High OI + Volume", value=True)
        use_tradingview = st.checkbox("Use TradingView charts", value=True)

        st.divider()
        st.write("Execution")
        st.warning("Live auto-trading is disabled. Use signals manually for now.")

    settings = replace(
        base_settings,
        data_mode=DATA_MODES[data_label],
        discovery_limit=discovery_limit,
        prefilter_limit=discovery_limit,
        deep_scan_limit=deep_scan_limit,
        candle_limit=candle_limit,
        render_charts=False,
        auto_scan_enabled=auto_refresh,
        auto_scan_interval_seconds=refresh_seconds,
    )
    coach = CoachMirandaMiner(settings)

    status_cols = st.columns(5)
    status_cols[0].metric("Data Mode", settings.data_mode)
    status_cols[1].metric("Analyzer", settings.analyzer_mode)
    status_cols[2].metric("Trading Mode", settings.trading_mode)
    status_cols[3].metric("Telegram", "On" if coach.telegram.configured else "Off")
    status_cols[4].metric("Coinalyze", "On" if settings.coinalyze_api_key else "Off")
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

    if clear_cache:
        st.session_state.pop("scan_cache", None)
        st.success("Scan cache cleared.")

    scanner_tab, oi_tab, backtest_tab, history_tab = st.tabs(
        ["Scanner", "High OI", "Backtest", "History"]
    )
    with scanner_tab:
        if run_scan or auto_refresh:
            render_scan(
                coach,
                use_tradingview,
                show_oi=False,
                force_refresh=run_scan,
                cache_seconds=refresh_seconds,
            )
        else:
            st.info("Press Scan Now to look for setups.")

    with oi_tab:
        if show_oi:
            cached_payload = _cached_scan_payload()
            if cached_payload is not None:
                _, scores, _ = cached_payload
                render_high_oi_from_scores(scores)
            else:
                render_high_oi(coach)
        else:
            st.info("Enable High OI + Volume in the sidebar.")

    with backtest_tab:
        render_backtest(coach)

    with history_tab:
        if show_history:
            render_history(coach)
            render_outcomes(coach)
            render_calibration(coach)
        else:
            st.info("Enable signal history in the sidebar.")

    if auto_refresh:
        time.sleep(refresh_seconds)
        st.rerun()


def render_scan(
    coach: CoachMirandaMiner,
    use_tradingview: bool = True,
    show_oi: bool = True,
    force_refresh: bool = False,
    cache_seconds: int = 900,
) -> None:
    cache_key = _scan_cache_key(coach.settings)
    cached = st.session_state.get("scan_cache")
    cache_is_valid = (
        cached is not None
        and cached.get("key") == cache_key
        and time.time() - cached.get("saved_at", 0) < cache_seconds
    )
    if cache_is_valid and not force_refresh:
        summary, scores, results = cached["payload"]
        cache_age = int(time.time() - cached.get("saved_at", 0))
        st.caption(f"Using cached scan result from {cache_age}s ago. Press Scan Now to force a fresh scan.")
    else:
        with st.spinner("Scanning top universe, ranking candidates, and deep-analyzing setups..."):
            summary, scores, results = coach.scan_setups()
        st.session_state["scan_cache"] = {
            "key": cache_key,
            "saved_at": time.time(),
            "payload": (summary, scores, results),
        }

    status_cols = st.columns(6)
    status_cols[0].metric("Candidates Scanned", summary.candidates_scanned)
    status_cols[1].metric("Deep Analyzed", summary.deep_analyzed)
    status_cols[2].metric("Failed Symbols", summary.failed_symbols)
    status_cols[3].metric("Duration", f"{summary.duration_seconds or 0:.1f}s")
    status_cols[4].metric("Workers", summary.worker_count)
    status_cols[5].metric("Coinalyze", "On" if summary.coinalyze_enabled else "Off")
    st.caption(f"Last scan: {summary.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if summary.market_regime is not None:
        st.subheader("Market Regime")
        regime_cols = st.columns(4)
        regime_cols[0].metric("Mode", summary.market_regime.risk_mode)
        regime_cols[1].metric("Trend Score", f"{summary.market_regime.trend_score:.2f}")
        regime_cols[2].metric("BTC 24h", f"{summary.market_regime.btc_change_24h_pct:.2f}%")
        eth_change = summary.market_regime.eth_change_24h_pct
        regime_cols[3].metric("ETH 24h", f"{eth_change:.2f}%" if eth_change is not None else "n/a")
        st.write(summary.market_regime.reason)
    for warning in summary.warnings[:6]:
        st.caption(warning)

    render_prefilter(scores)
    render_short_candidates(results)
    if show_oi:
        render_high_oi_from_scores(scores)
    render_deep_scan(results, use_tradingview)


def render_prefilter(scores) -> None:
    st.subheader("Top 100 Prefilter")
    if not scores:
        st.info("No prefilter candidates available.")
        return
    frame = _score_frame(scores[:100])
    st.dataframe(
        frame.head(25),
        use_container_width=True,
        hide_index=True,
        column_config=_score_column_config(),
    )
    if len(frame) > 25:
        with st.expander("Show full top 100 prefilter"):
            st.dataframe(
                frame,
                use_container_width=True,
                hide_index=True,
                column_config=_score_column_config(),
            )


def _score_frame(scores) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rank": item.rank,
                "symbol": item.symbol,
                "score": item.score,
                "volume_24h_usd": item.volume_24h_usd,
                "price_change_24h_pct": item.price_change_24h_pct,
                "oi_change_24h_pct": item.oi_change_24h_pct,
                "relative_volume": item.relative_volume,
                "btc_regime_ok": item.btc_regime_ok,
                "why": " ".join(item.prefilter_reasons[:3]),
            }
            for item in scores[:100]
        ]
    )


def _score_column_config() -> dict:
    return {
        "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
        "price_change_24h_pct": st.column_config.NumberColumn("24h %", format="%.2f%%"),
        "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
        "relative_volume": st.column_config.NumberColumn("15m Rel Vol", format="%.2fx"),
        "score": st.column_config.NumberColumn("Score", format="%.1f"),
    }


def render_deep_scan(results, use_tradingview: bool) -> None:
    st.subheader("Deep Scan Results")
    rows = sorted(
        [
            {
                "rank": result.score.rank,
                "symbol": result.candidate.route_symbol,
                "source": result.candidate.exchange_id,
                "score": result.score.score,
                "setup": result.thesis.setup.value,
                "signal": result.thesis.signal.value,
                "direction": result.thesis.direction,
                "confidence": result.thesis.confidence,
                "entry": result.thesis.entry,
                "stop": result.thesis.stop_loss,
                "target_1": result.thesis.targets[0] if result.thesis.targets else None,
                "grade": alert_grade(result.thesis, result.validation, result.score),
                "approved": result.validation.approved,
                "alert_sent": result.alert_sent,
            }
            for result in results
        ],
        key=lambda item: (
            SIGNAL_PRIORITY.get(item.get("signal", "reject"), 9),
            int(item["rank"]),
        ),
    )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No deep scan candidates produced a setup table.")

    for result in results:
        candidate = result.candidate
        pack = result.pack
        thesis = result.thesis
        validation = result.validation
        with st.expander(
            (
                f"#{result.score.rank} {candidate.route_symbol} - "
                f"{thesis.direction.upper()} {thesis.setup.value} / {thesis.signal.value}"
            ),
            expanded=thesis.signal.value in {"watch", "enter"},
        ):
            timeframe = st.selectbox(
                "Chart timeframe",
                list(pack.candles.keys()),
                index=max(list(pack.candles.keys()).index("15m"), 0)
                if "15m" in pack.candles
                else 0,
                key=f"tf-{candidate.route_symbol}",
            )
            if use_tradingview:
                components.html(
                    _tradingview_widget(candidate.route_symbol, timeframe),
                    height=TRADINGVIEW_HEIGHT,
                )
                st.caption("TradingView tools are available inside the full-width chart.")
            else:
                st.plotly_chart(
                    _candlestick(pack, timeframe, thesis),
                    use_container_width=True,
                    key=f"chart-{candidate.route_symbol}-{timeframe}",
                )

            st.divider()
            detail_cols = st.columns(4)
            with detail_cols[0]:
                st.metric("Signal", thesis.signal.value.upper())
                st.metric("Direction", thesis.direction.upper())
            with detail_cols[1]:
                st.metric("Confidence", f"{thesis.confidence:.0%}")
                st.metric("Rank Score", f"{result.score.score:.1f}")
            with detail_cols[2]:
                st.metric("Risk/Reward", thesis.risk_reward or "n/a")
                st.write("Entry", _fmt(thesis.entry))
            with detail_cols[3]:
                st.write("Stop", _fmt(thesis.stop_loss))
                st.write("Targets", ", ".join(_fmt(item) for item in thesis.targets) or "n/a")

            detail_left, detail_right = st.columns(2)
            with detail_left:
                st.write("Evidence")
                for reason in result.score.prefilter_reasons[:3]:
                    st.write(f"- {reason}")
                for item in thesis.evidence:
                    st.write(f"- {item}")
                if candidate.trading_link:
                    st.link_button("Open Trading Page", candidate.trading_link)
            with detail_right:
                st.write("Validation")
                if validation.approved:
                    st.success("Approved")
                else:
                    for reason in validation.reasons:
                        st.warning(reason)


def render_short_candidates(results) -> None:
    short_rows = [
        {
            "rank": result.score.rank,
            "symbol": result.candidate.route_symbol,
            "setup": result.thesis.setup.value,
            "signal": result.thesis.signal.value,
            "confidence": result.thesis.confidence,
            "entry": result.thesis.entry,
            "stop": result.thesis.stop_loss,
            "target_1": result.thesis.targets[0] if result.thesis.targets else None,
            "grade": alert_grade(result.thesis, result.validation, result.score),
        }
        for result in results
        if result.thesis.direction == "short"
    ]
    st.subheader("Short Candidates")
    if not short_rows:
        st.caption("No short setups in the latest deep scan.")
        return
    st.dataframe(
        pd.DataFrame(short_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
            "stop": st.column_config.NumberColumn("Stop", format="%.6f"),
            "target_1": st.column_config.NumberColumn("Target 1", format="%.6f"),
        },
    )


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
                "oi_change_24h_pct": row.open_interest_change_24h_pct,
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
            "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
            "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
            "score": st.column_config.NumberColumn("OI/Vol Score", format="%.0f"),
            "price": st.column_config.NumberColumn("Price", format="$%.4f"),
        },
    )


def render_high_oi_from_scores(scores) -> None:
    st.subheader("High OI + Volume")
    rows = [
        item
        for item in scores
        if item.oi_change_24h_pct is not None or item.volume_24h_usd is not None
    ]
    if not rows:
        st.info("No OI or volume rows available from the current scan.")
        return
    frame = pd.DataFrame(
        [
            {
                "rank": item.rank,
                "symbol": item.symbol,
                "score": item.score,
                "oi_change_24h_pct": item.oi_change_24h_pct,
                "volume_24h_usd": item.volume_24h_usd,
                "relative_volume": item.relative_volume,
            }
            for item in sorted(
                rows,
                key=lambda row: (
                    abs(row.oi_change_24h_pct or 0.0),
                    row.volume_24h_usd or 0.0,
                ),
                reverse=True,
            )[:30]
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
            "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
            "relative_volume": st.column_config.NumberColumn("15m Rel Vol", format="%.2fx"),
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
        },
    )


def render_history(coach: CoachMirandaMiner) -> None:
    st.subheader("Active WATCH/ENTER Lifecycle")
    active_rows = (
        coach.journal.recent_active_setups(50)
        if hasattr(coach.journal, "recent_active_setups")
        else []
    )
    if active_rows:
        active_frame = pd.DataFrame(active_rows)
        st.download_button(
            "Download Active Setups CSV",
            active_frame.to_csv(index=False),
            file_name="active_setups.csv",
            mime="text/csv",
        )
        st.dataframe(
            active_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
                "stop_loss": st.column_config.NumberColumn("Stop", format="%.6f"),
                "target": st.column_config.NumberColumn("Target", format="%.6f"),
                "score": st.column_config.NumberColumn("Score", format="%.1f"),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            },
        )
    else:
        st.caption("No active setup lifecycle rows yet.")

    st.subheader("Recent Signal History")
    rows = coach.journal.recent_theses(20)
    if not rows:
        st.caption("No saved signals yet.")
    else:
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

    st.subheader("Recent Alerts")
    alerts = coach.journal.recent_alerts(20)
    if not alerts:
        st.caption("No Telegram alerts sent yet.")
        return
    alert_frame = pd.DataFrame(
        [
            {
                "time": row["created_at"],
                "symbol": row["symbol"],
                "setup": row["setup"],
                "signal": row["signal"],
            }
            for row in alerts
        ]
    )
    st.download_button(
        "Download Alerts CSV",
        alert_frame.to_csv(index=False),
        file_name="telegram_alerts.csv",
        mime="text/csv",
    )
    st.dataframe(alert_frame, use_container_width=True, hide_index=True)


def render_calibration(coach: CoachMirandaMiner) -> None:
    st.subheader("Setup Calibration")
    rows = coach.journal.setup_calibration(500)
    if not rows:
        st.caption("No setup score history yet.")
        return
    frame = pd.DataFrame(rows)
    st.download_button(
        "Download Setup Calibration CSV",
        frame.to_csv(index=False),
        file_name="setup_calibration.csv",
        mime="text/csv",
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "avg_score": st.column_config.NumberColumn("Avg Score", format="%.1f"),
            "avg_confidence": st.column_config.NumberColumn("Avg Confidence", format="%.2f"),
            "avg_relative_volume": st.column_config.NumberColumn("Avg Rel Vol", format="%.2fx"),
            "avg_oi_change_24h_pct": st.column_config.NumberColumn("Avg OI 24h %", format="%.2f%%"),
        },
    )


def render_outcomes(coach: CoachMirandaMiner) -> None:
    st.subheader("Outcome Tracking")
    if st.button("Update Due Outcomes"):
        with st.spinner("Checking 15m candles for target/stop/time outcomes..."):
            updated = coach.update_signal_outcomes()
        st.success(f"Updated {updated} due outcome rows.")

    summary = coach.journal.outcome_summary(500)
    if summary:
        summary_frame = pd.DataFrame(summary)
        st.download_button(
            "Download Outcome Summary CSV",
            summary_frame.to_csv(index=False),
            file_name="outcome_summary.csv",
            mime="text/csv",
        )
        st.dataframe(
            summary_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "avg_return_pct": st.column_config.NumberColumn("Avg Return", format="%.2f%%"),
            },
        )

    rows = coach.journal.recent_signal_outcomes(50)
    if not rows:
        st.caption("No tracked signal outcomes yet.")
        return
    outcome_frame = pd.DataFrame(rows)
    st.download_button(
        "Download Recent Outcomes CSV",
        outcome_frame.to_csv(index=False),
        file_name="recent_outcomes.csv",
        mime="text/csv",
    )
    st.dataframe(
        outcome_frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
            "stop_loss": st.column_config.NumberColumn("Stop", format="%.6f"),
            "target": st.column_config.NumberColumn("Target", format="%.6f"),
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
            "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            "return_pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
        },
    )
    candle_rows = (
        coach.journal.recent_candle_samples(50)
        if hasattr(coach.journal, "recent_candle_samples")
        else []
    )
    if candle_rows:
        st.subheader("Historical Candle Samples")
        candle_frame = pd.DataFrame(candle_rows)
        st.download_button(
            "Download Candle Sample Log CSV",
            candle_frame.to_csv(index=False),
            file_name="candle_samples.csv",
            mime="text/csv",
        )
        st.dataframe(candle_frame, use_container_width=True, hide_index=True)


def render_backtest(coach: CoachMirandaMiner) -> None:
    st.subheader("Strategy Backtest")
    cols = st.columns(4)
    with cols[0]:
        symbol = st.text_input("Symbol", value=coach.settings.symbol.replace("USDT", "USD"))
    with cols[1]:
        timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=0)
    with cols[2]:
        strategy = st.selectbox("Strategy", ["miranda", "ma"], index=0)
    with cols[3]:
        side = st.selectbox("Side", ["both", "long", "short"], index=0)

    left_action, right_action = st.columns(2)
    run_single = left_action.button("Run Backtest", type="primary", use_container_width=True)
    run_batch = right_action.button("Run Batch Top Coins", use_container_width=True)
    run_walk = st.button("Run Walk-Forward Test", use_container_width=True)
    if not run_single and not run_batch and not run_walk:
        st.caption("Backtests use the configured data source and candle limit.")
        return

    if run_walk:
        with st.spinner("Running walk-forward validation..."):
            try:
                result = coach.walk_forward_backtest(symbol, timeframe, strategy, side)
            except Exception as exc:
                st.error("Walk-forward test failed.")
                st.code(str(exc))
                return
        rows = [
            {
                "segment": "train",
                "trades": result["train"].trades,
                "win_rate": result["train"].win_rate,
                "expectancy_pct": result["train"].expectancy_pct,
                "return_pct": result["train"].total_return_pct,
                "drawdown_pct": result["train"].max_drawdown_pct,
            },
            {
                "segment": "test",
                "trades": result["test"].trades,
                "win_rate": result["test"].win_rate,
                "expectancy_pct": result["test"].expectancy_pct,
                "return_pct": result["test"].total_return_pct,
                "drawdown_pct": result["test"].max_drawdown_pct,
            },
        ]
        st.metric("Expectancy Degradation", f"{result['degradation_pct']:.2f}%")
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "expectancy_pct": st.column_config.NumberColumn("Expectancy", format="%.2f%%"),
                "return_pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
                "drawdown_pct": st.column_config.NumberColumn("Drawdown", format="%.2f%%"),
            },
        )
        return

    if run_batch:
        with st.spinner("Running batch backtests across the current universe..."):
            rows = coach.batch_backtest(
                limit=coach.settings.backtest_limit,
                timeframe=timeframe,
                strategy=strategy,
                side=side,
            )
        if not rows:
            st.info("Batch backtest did not return any rows from the current data source.")
            return
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "return_pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
                "drawdown_pct": st.column_config.NumberColumn("Drawdown", format="%.2f%%"),
                "profit_factor": st.column_config.NumberColumn("Profit Factor", format="%.2f"),
                "expectancy_pct": st.column_config.NumberColumn("Expectancy", format="%.2f%%"),
            },
        )
        return

    with st.spinner("Running backtest..."):
        try:
            result = coach.backtest(symbol, timeframe, strategy, side)
        except Exception as exc:
            st.error("Backtest failed.")
            st.code(str(exc))
            return

    metrics = st.columns(6)
    metrics[0].metric("Trades", result.trades)
    metrics[1].metric("Win Rate", f"{result.win_rate:.1%}")
    metrics[2].metric("Return", f"{result.total_return_pct:.2f}%")
    metrics[3].metric("Drawdown", f"{result.max_drawdown_pct:.2f}%")
    metrics[4].metric("Profit Factor", f"{result.profit_factor:.2f}")
    metrics[5].metric("Expectancy", f"{result.expectancy_pct:.2f}%")
    st.write(f"Longs: {result.long_trades} | Shorts: {result.short_trades}")
    if result.setup_stats:
        setup_rows = [
            {"setup": setup, **stats}
            for setup, stats in sorted(
                result.setup_stats.items(),
                key=lambda item: item[1].get("expectancy_pct", 0.0),
                reverse=True,
            )
        ]
        st.write("Setup Breakdown")
        st.dataframe(
            pd.DataFrame(setup_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "expectancy_pct": st.column_config.NumberColumn("Expectancy", format="%.2f%%"),
            },
        )
    if result.sample_trades:
        st.dataframe(pd.DataFrame(result.sample_trades), use_container_width=True, hide_index=True)
    st.code(result.format())


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


def _tradingview_widget(symbol: str, timeframe: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        html, body {{
          height: 100%;
          width: 100%;
          margin: 0;
          overflow: hidden;
          background: #0b0e11;
        }}
        .tradingview-widget-container,
        .tradingview-widget-container__widget {{
          height: 100%;
          width: 100%;
        }}
      </style>
    </head>
    <body>
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
        "width": "100%",
        "height": {TRADINGVIEW_HEIGHT},
        "symbol": "{_tradingview_symbol(symbol)}",
        "interval": "{_tradingview_interval(timeframe)}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "withdateranges": true,
        "hide_side_toolbar": false,
        "details": true,
        "hotlist": true,
        "calendar": false,
        "support_host": "https://www.tradingview.com"
      }}
      </script>
    </div>
    </body>
    </html>
    """


def _tradingview_symbol(symbol: str) -> str:
    base = symbol.split("/")[0].upper()
    return f"COINBASE:{base}USD"


def _tradingview_interval(timeframe: str) -> str:
    return {
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D",
    }.get(timeframe, "15")


def _mode_index(mode: str) -> int:
    values = list(DATA_MODES.values())
    return values.index(mode) if mode in values else 0


def _refresh_index(seconds: int) -> int:
    values = [60, 180, 300, 900]
    return values.index(seconds) if seconds in values else 3


def _scan_cache_key(settings: Settings) -> tuple:
    return (
        settings.data_mode,
        settings.prefilter_limit,
        settings.deep_scan_limit,
        settings.candle_limit,
        tuple(settings.timeframes),
        settings.min_confidence,
        settings.min_risk_reward,
        settings.min_volume_24h_usd,
        bool(settings.coinalyze_api_key),
        settings.telegram_min_signal,
        getattr(settings, "min_alert_grade", "B"),
        getattr(settings, "require_watch_before_enter", False),
        getattr(settings, "active_setup_ttl_minutes", 240),
        settings.scan_workers,
        settings.prefilter_candle_limit,
    )


def _cached_scan_payload():
    cached = st.session_state.get("scan_cache")
    if cached is None:
        return None
    return cached.get("payload")


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
