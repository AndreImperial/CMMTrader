from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from coach_miranda_miner.alerts import alert_grade
from coach_miranda_miner.coach import CoachMirandaMiner
from coach_miranda_miner.config import Settings


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"

app = FastAPI(title="CMMTrader API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def _settings(data_mode: str | None = None) -> Settings:
    base = Settings.from_env()
    if data_mode:
        return replace(base, data_mode=data_mode)
    return base


def _coach(data_mode: str | None = None) -> CoachMirandaMiner:
    return CoachMirandaMiner(_settings(data_mode))


@app.get("/api/health")
def health() -> dict[str, Any]:
    settings = _settings()
    coach = CoachMirandaMiner(settings)
    return {
        "status": "ok",
        "app": "CMMTrader",
        "tradingMode": settings.trading_mode,
        "dataMode": settings.data_mode,
        "analyzerMode": settings.analyzer_mode,
        "discoveryMode": settings.discovery_mode,
        "telegramConfigured": coach.telegram.configured,
        "coinalyzeConfigured": bool(settings.coinalyze_api_key),
        "paperOnly": settings.trading_mode == "paper",
    }


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    settings = _settings()
    coach = CoachMirandaMiner(settings)
    return {
        "health": health(),
        "doctor": coach.doctor().splitlines(),
        "guardrails": {
            "maxPositionUsd": settings.max_position_usd,
            "maxDailyLossUsd": settings.max_daily_loss_usd,
            "btcKillSwitchDropPct": settings.btc_kill_switch_drop_pct,
            "minVolume24hUsd": settings.min_volume_24h_usd,
            "minRiskReward": settings.min_risk_reward,
            "minConfidence": settings.min_confidence,
        },
        "scanner": {
            "prefilterLimit": settings.prefilter_limit,
            "deepScanLimit": settings.deep_scan_limit,
            "scanWorkers": settings.scan_workers,
            "candleLimit": settings.candle_limit,
        },
    }


@app.post("/api/scan")
def scan(data_mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        coach = _coach(data_mode)
        summary, scores, results = coach.scan_setups()
        return {
            "summary": summary.model_dump(mode="json"),
            "scores": [score.model_dump(mode="json") for score in scores[:100]],
            "results": [_deep_result(result) for result in results],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scalp")
def scalp(data_mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        coach = _coach(data_mode)
        summary, results = coach.scan_scalps()
        return {
            "summary": summary.model_dump(mode="json"),
            "results": [_scalp_result(result) for result in results],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/open-interest")
def open_interest(data_mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        rows, warnings = _coach(data_mode).high_oi_watchlist()
        return {
            "warnings": warnings,
            "rows": [row.__dict__ for row in rows],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/backtest")
def backtest(
    symbol: str = Query(default="BTC/USD"),
    timeframe: str = Query(default="1h"),
    strategy: str = Query(default="miranda"),
    side: str = Query(default="both"),
    data_mode: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        result = _coach(data_mode).backtest(symbol, timeframe, strategy, side)
        return {
            "result": result.__dict__,
            "formatted": result.format(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/journal")
def journal() -> dict[str, Any]:
    coach = _coach()
    return {
        "activeSetups": coach.journal.recent_active_setups(50)
        if hasattr(coach.journal, "recent_active_setups")
        else [],
        "theses": coach.journal.recent_theses(30),
        "alerts": coach.journal.recent_alerts(30),
        "outcomes": coach.journal.recent_signal_outcomes(30),
        "calibration": coach.journal.setup_calibration(500),
    }


def _deep_result(result) -> dict[str, Any]:
    thesis = result.thesis
    validation = result.validation
    return {
        "rank": result.score.rank,
        "symbol": result.candidate.route_symbol,
        "source": result.candidate.exchange_id,
        "setup": thesis.setup.value,
        "signal": thesis.signal.value,
        "direction": thesis.direction,
        "confidence": thesis.confidence,
        "entry": thesis.entry,
        "stopLoss": thesis.stop_loss,
        "targets": thesis.targets,
        "riskReward": thesis.risk_reward,
        "grade": alert_grade(thesis, validation, result.score),
        "approved": validation.approved,
        "alertSent": result.alert_sent,
        "score": result.score.score,
        "volume24hUsd": result.candidate.volume_24h_usd,
        "evidence": thesis.evidence,
        "validationReasons": validation.reasons,
        "prefilterReasons": result.score.prefilter_reasons,
        "tradingLink": result.candidate.trading_link,
    }


def _scalp_result(result) -> dict[str, Any]:
    return {
        "symbol": result.candidate.route_symbol,
        "source": result.candidate.exchange_id,
        "setup": result.thesis.setup.value,
        "signal": result.thesis.signal.value,
        "direction": result.thesis.direction,
        "confidence": result.thesis.confidence,
        "entry": result.thesis.entry,
        "stopLoss": result.thesis.stop_loss,
        "targets": result.thesis.targets,
        "score": result.score.score,
        "grade": result.quality.grade,
        "scannedAt": result.scanned_at.isoformat(),
        "executionCandleTime": result.execution_candle_time.isoformat()
        if result.execution_candle_time
        else None,
        "latestCandleTime": result.latest_candle_time.isoformat()
        if result.latest_candle_time
        else None,
        "quality": result.quality.reasons,
        "validationReasons": result.validation.reasons,
        "alertSent": result.alert_sent,
    }


@app.get("/{full_path:path}")
def frontend(full_path: str):
    file_path = FRONTEND_DIST / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "React frontend has not been built yet.",
        "build": "Run `pnpm --dir frontend install` and `pnpm --dir frontend build`.",
    }
