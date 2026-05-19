from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
import math
from threading import Lock
import time

from ccxt import BaseError as CcxtError
import requests

from .alerts import AlertFormatter
from .analyzer import OpenAIVisionAnalyzer, RuleBasedAnalyzer
from .backtest import (
    BacktestResult,
    MirandaStrategyBacktester,
    MovingAverageBacktester,
    StrategyBacktestConfig,
)
from .broker import PaperBroker
from .charts import ChartRenderer
from .config import Settings
from .data import MarketData
from .discovery import DEFAULT_MAJORS, DiscoveryEngine, ExchangeMomentumDiscoveryEngine
from .exchanges import (
    CoinGeckoRouter,
    CoinPaprikaRouter,
    CoinbaseRouter,
    ExchangeRouter,
    FixtureExchangeRouter,
    YahooFinanceRouter,
)
from .gatekeepers import Gatekeeper
from .intelligence import IntelligenceGatherer
from .journal import Journal
from .market_cap import CoinMarketCapProvider, StaticMarketCapProvider
from .miner import SignalMiner
from .models import (
    Candidate,
    IntelligencePack,
    MarketRegime,
    ScanSummary,
    SetupScore,
    SignalState,
    TradeThesis,
    ValidationResult,
)
from .news import CryptoPanicNewsProvider, EmptyNewsProvider
from .oi import OISnapshot, OpenInterestScanner
from .risk import RiskManager
from .telegram import TelegramAlerter
from .validator import ThesisValidator


@dataclass(frozen=True)
class DeepScanResult:
    candidate: Candidate
    score: SetupScore
    pack: IntelligencePack
    thesis: TradeThesis
    validation: ValidationResult
    alert_sent: bool


class CoachMirandaMiner:
    def __init__(self, settings: Settings) -> None:
        if settings.trading_mode != "paper":
            raise ValueError("Only paper mode is supported in this scaffold.")

        self.settings = settings
        self.market_data = MarketData(settings.exchange_id)
        self.miner = SignalMiner(
            short_ma=settings.short_ma,
            long_ma=settings.long_ma,
            rsi_period=settings.rsi_period,
            rsi_buy_max=settings.rsi_buy_max,
            rsi_sell_min=settings.rsi_sell_min,
        )
        self.risk = RiskManager(settings.max_position_usd, settings.max_daily_loss_usd)
        self.broker = PaperBroker(settings.starting_cash)
        self.journal = Journal(settings.journal_db)
        self.router = (
            FixtureExchangeRouter(settings.exchange_ids)
            if settings.data_mode == "fixture"
            else CoinGeckoRouter(settings.exchange_ids)
            if settings.data_mode == "coingecko"
            else YahooFinanceRouter(settings.exchange_ids)
            if settings.data_mode == "yahoo"
            else CoinPaprikaRouter(settings.exchange_ids)
            if settings.data_mode == "paprika"
            else CoinbaseRouter(settings.exchange_ids)
            if settings.data_mode == "coinbase"
            else ExchangeRouter(settings.exchange_ids)
        )
        self.discovery = self._build_discovery()
        self.gatekeeper = Gatekeeper(
            self.router,
            settings.btc_kill_switch_drop_pct,
            settings.min_volume_24h_usd,
            settings.quote_currency,
        )
        chart_renderer = ChartRenderer(settings.chart_dir) if settings.render_charts else None
        news_provider = (
            CryptoPanicNewsProvider(settings.cryptopanic_api_key)
            if settings.cryptopanic_api_key
            else EmptyNewsProvider()
        )
        self.intelligence = IntelligenceGatherer(
            self.router,
            settings.timeframes,
            settings.candle_limit,
            chart_renderer,
            news_provider,
        )
        self.analyzer = (
            OpenAIVisionAnalyzer(settings.openai_model)
            if settings.analyzer_mode == "openai"
            else RuleBasedAnalyzer()
        )
        self.validator = ThesisValidator(
            settings.min_risk_reward,
            settings.min_confidence,
            settings.max_stop_atr_multiple,
        )
        self.alerts = AlertFormatter()
        self.telegram = TelegramAlerter(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
        )
        self.backtester = MovingAverageBacktester(
            settings.short_ma,
            settings.long_ma,
            settings.rsi_period,
            settings.rsi_buy_max,
            settings.backtest_fee_bps,
            settings.backtest_slippage_bps,
            settings.backtest_stop_atr_multiple,
            settings.backtest_target_r_multiple,
        )
        self.oi_scanner = OpenInterestScanner(
            self.router,
            settings.oi_bases,
            settings.coinalyze_api_key,
        )

    def scan_setups(self) -> tuple[ScanSummary, list[SetupScore], list[DeepScanResult]]:
        started_at = time.perf_counter()
        warnings: list[str] = []
        worker_count = max(1, self.settings.scan_workers)
        self._scan_ticker_cache = {}
        self._scan_candle_cache = {}
        self._scan_cache_lock = Lock()
        try:
            market_regime = self.gatekeeper.market_regime()
        except (CcxtError, requests.RequestException, ValueError) as exc:
            summary = ScanSummary(
                candidates_scanned=0,
                deep_analyzed=0,
                warnings=[f"Market regime unavailable: {exc}"],
                coinalyze_enabled=bool(self.settings.coinalyze_api_key),
                duration_seconds=_elapsed(started_at),
                worker_count=worker_count,
            )
            return summary, [], []

        try:
            candidates = self.discovery.discover(self.settings.prefilter_limit)
        except (CcxtError, requests.RequestException, ValueError) as exc:
            summary = ScanSummary(
                candidates_scanned=0,
                deep_analyzed=0,
                warnings=[f"Discovery unavailable: {exc}", *warnings],
                coinalyze_enabled=bool(self.settings.coinalyze_api_key),
                market_regime=market_regime,
                duration_seconds=_elapsed(started_at),
                worker_count=worker_count,
            )
            return summary, [], []

        oi_by_base = self._coinalyze_rows_for_candidates(candidates, warnings)

        failed_symbols = 0
        scored: list[tuple[Candidate, SetupScore]] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._score_candidate, candidate, oi_by_base, market_regime): candidate
                for candidate in candidates
            }
            done, pending = wait(futures, timeout=self.settings.fetch_timeout_seconds)
            for future in done:
                candidate = futures[future]
                try:
                    result = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
                    failed_symbols += 1
                    warnings.append(f"{candidate.route_symbol} prefilter skipped: {exc}")
                    continue
                if result is None:
                    failed_symbols += 1
                    continue
                scored.append(result)
            for future in pending:
                failed_symbols += 1
                candidate = futures[future]
                future.cancel()
                warnings.append(
                    f"{candidate.route_symbol} prefilter timed out after "
                    f"{self.settings.fetch_timeout_seconds}s."
                )

        ranked_pairs = sorted(scored, key=lambda item: item[1].score, reverse=True)
        ranked: list[tuple[Candidate, SetupScore]] = []
        for rank, (candidate, score) in enumerate(ranked_pairs, start=1):
            ranked.append((candidate, score.model_copy(update={"rank": rank})))

        deep_results: list[DeepScanResult] = []
        deep_pairs = ranked[: self.settings.deep_scan_limit]
        with ThreadPoolExecutor(max_workers=max(1, min(worker_count, len(deep_pairs) or 1))) as executor:
            futures = {
                executor.submit(self._deep_scan_candidate, candidate, score, market_regime): (candidate, score)
                for candidate, score in deep_pairs
            }
            done, pending = wait(
                futures,
                timeout=max(self.settings.fetch_timeout_seconds, self.settings.fetch_timeout_seconds * len(deep_pairs)),
            )
            for future in done:
                candidate, _ = futures[future]
                try:
                    result = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
                    failed_symbols += 1
                    warnings.append(f"{candidate.route_symbol} deep scan failed: {exc}")
                    continue
                if result is None:
                    continue
                deep_results.append(result)
            for future in pending:
                candidate, _ = futures[future]
                future.cancel()
                failed_symbols += 1
                warnings.append(f"{candidate.route_symbol} deep scan timed out.")

        deep_results = sorted(deep_results, key=lambda item: item.score.rank)
        for result in deep_results:
            self._record_deep_result(result)

        summary = ScanSummary(
            candidates_scanned=len(ranked),
            deep_analyzed=len(deep_results),
            warnings=warnings,
            coinalyze_enabled=bool(self.settings.coinalyze_api_key),
            market_regime=market_regime,
            duration_seconds=_elapsed(started_at),
            failed_symbols=failed_symbols,
            worker_count=worker_count,
        )
        return summary, [score for _, score in ranked], deep_results

    def _score_candidate(
        self,
        candidate: Candidate,
        oi_by_base: dict[str, OISnapshot],
        market_regime: MarketRegime,
    ) -> tuple[Candidate, SetupScore]:
        ticker = self._cached_ticker(candidate.exchange_id, candidate.route_symbol)
        base = candidate.asset.base
        oi_row = oi_by_base.get(base)
        relative_volume = self._relative_volume_for(candidate, [])
        enriched = candidate.model_copy(
            update={
                "volume_24h_usd": ticker.quote_volume,
                "open_interest_change_24h_pct": oi_row.open_interest_change_24h_pct
                if oi_row
                else None,
            }
        )
        return (
            enriched,
            _setup_score(
                enriched,
                price_change_24h_pct=ticker.percentage,
                relative_volume=relative_volume,
                btc_regime_ok=market_regime.longs_allowed,
            ),
        )

    def _deep_scan_candidate(
        self,
        candidate: Candidate,
        score: SetupScore,
        market_regime: MarketRegime,
    ) -> DeepScanResult | None:
        if candidate.volume_24h_usd is not None and candidate.volume_24h_usd < self.settings.min_volume_24h_usd:
            return None
        gatherer = IntelligenceGatherer(
            self.router,
            self.settings.timeframes,
            self.settings.candle_limit,
            self.intelligence.chart_renderer,
            self.intelligence.news_provider,
            candle_fetcher=self._cached_candles,
        )
        pack = gatherer.gather(candidate, market_regime)
        thesis = self.analyzer.analyze(pack)
        atr = next((item.atr for item in pack.indicators if item.timeframe == "15m"), None)
        validation = self.validator.validate(thesis, market_regime, atr)
        message = self.alerts.format(candidate, thesis, validation, score)
        alert_sent = self.maybe_send_telegram_alert(candidate, thesis, validation, message)
        return DeepScanResult(
            candidate=candidate,
            score=score,
            pack=pack,
            thesis=thesis,
            validation=validation,
            alert_sent=alert_sent,
        )

    def _record_deep_result(self, result: DeepScanResult) -> None:
        thesis = result.thesis
        validation = result.validation
        score = result.score
        self.journal.record_thesis(
            symbol=thesis.symbol,
            setup=thesis.setup.value,
            signal=thesis.signal.value,
            direction=thesis.direction,
            confidence=thesis.confidence,
            approved=validation.approved,
            payload_json=thesis.model_dump_json(),
            validation_json=validation.model_dump_json(),
        )
        self.journal.record_setup_score(
            symbol=thesis.symbol,
            setup=thesis.setup.value,
            signal=thesis.signal.value,
            rank=score.rank,
            score=score.score,
            confidence=thesis.confidence,
            approved=validation.approved,
            volume_24h_usd=score.volume_24h_usd,
            oi_change_24h_pct=score.oi_change_24h_pct,
            relative_volume=score.relative_volume,
        )

    def _coinalyze_rows_for_candidates(
        self,
        candidates: list[Candidate],
        warnings: list[str],
    ) -> dict[str, OISnapshot]:
        if not self.settings.coinalyze_api_key:
            warnings.append("Coinalyze API key not configured; OI prefilter boost unavailable.")
            return {}
        bases = sorted({candidate.asset.base for candidate in candidates})
        scanner = OpenInterestScanner(self.router, bases, self.settings.coinalyze_api_key)
        rows = scanner.scan_coinalyze_only(warnings)
        return {row.symbol.split("/")[0]: row for row in rows}

    def _relative_volume_for(self, candidate: Candidate, warnings: list[str]) -> float | None:
        try:
            candles = self._cached_candles(
                candidate.exchange_id,
                candidate.route_symbol,
                "15m",
                self.settings.prefilter_candle_limit,
            )
        except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
            warnings.append(f"{candidate.route_symbol} relative volume unavailable: {exc}")
            return None
        if len(candles) < 21:
            return None
        latest = float(candles.iloc[-1]["volume"])
        average = float(candles["volume"].tail(21).head(20).mean())
        if average <= 0:
            return None
        return latest / average

    def _cached_ticker(self, exchange_id: str, symbol: str):
        cache_key = (exchange_id, symbol)
        with self._scan_cache_lock:
            if cache_key in self._scan_ticker_cache:
                return self._scan_ticker_cache[cache_key]
        ticker = self.router.fetch_ticker(exchange_id, symbol)
        with self._scan_cache_lock:
            self._scan_ticker_cache[cache_key] = ticker
        return ticker

    def _cached_candles(self, exchange_id: str, symbol: str, timeframe: str, limit: int):
        cache_key = (exchange_id, symbol, timeframe, limit)
        with self._scan_cache_lock:
            if cache_key in self._scan_candle_cache:
                return self._scan_candle_cache[cache_key].copy()
        candles = self.router.fetch_candles(exchange_id, symbol, timeframe, limit)
        with self._scan_cache_lock:
            self._scan_candle_cache[cache_key] = candles.copy()
        return candles.copy()

    def _build_discovery(self):
        if self.settings.discovery_mode == "cmc" and self.settings.coinmarketcap_api_key:
            return DiscoveryEngine(
                self.router,
                self.settings.quote_currency,
                CoinMarketCapProvider(self.settings.coinmarketcap_api_key),
                self.settings.discovery_pool_limit,
                self.settings.min_market_cap_usd,
            )
        if self.settings.discovery_mode == "static":
            return DiscoveryEngine(
                self.router,
                self.settings.quote_currency,
                StaticMarketCapProvider(DEFAULT_MAJORS),
                self.settings.discovery_pool_limit,
                self.settings.min_market_cap_usd,
            )
        return ExchangeMomentumDiscoveryEngine(
            self.router,
            self.settings.exchange_ids,
            self.settings.quote_currency,
            self.settings.min_volume_24h_usd,
            DEFAULT_MAJORS,
        )

    def run_once(self) -> str:
        candles = self.market_data.fetch_candles(
            self.settings.symbol,
            self.settings.timeframe,
            self.settings.candle_limit,
        )
        signal = self.miner.mine(candles)
        risk_decision = self.risk.evaluate(signal.action, daily_pnl=0.0)

        self.journal.record_decision(
            symbol=self.settings.symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            reason=signal.reason,
            approved=risk_decision.approved,
            risk_reason=risk_decision.reason,
        )

        if not risk_decision.approved:
            return (
                f"Coach Miranda Miner: {signal.action.upper()} skipped for "
                f"{self.settings.symbol}. {signal.reason} Risk: {risk_decision.reason}"
            )

        fill = self.broker.place_order(
            signal.action,
            signal.price,
            risk_decision.notional_usd,
        )
        self.journal.record_fill(
            fill.action,
            fill.quantity,
            fill.price,
            fill.notional_usd,
            fill.message,
        )
        return (
            f"Coach Miranda Miner: {fill.message} {fill.quantity:.8f} "
            f"at {fill.price:.2f} ({fill.notional_usd:.2f} USD). "
            f"Signal reason: {signal.reason}"
        )

    def scan(self) -> list[str]:
        summary, _, results = self.scan_setups()
        if summary.market_regime is None:
            return [
                "Live data is not available right now.",
                f"Data mode: {self.settings.data_mode}",
                f"Reason: {'; '.join(summary.warnings)}",
                "Try DATA_MODE=paprika for hosted free prices, or DATA_MODE=fixture for offline demo mode.",
            ]
        messages: list[str] = []

        if self.settings.data_mode == "fixture":
            messages.append(
                "DEMO DATA MODE: prices are synthetic and repeatable. "
                "Use DATA_MODE=live for updating exchange prices."
            )

        for result in results:
            messages.append(
                self.alerts.format(
                    result.candidate,
                    result.thesis,
                    result.validation,
                    result.score,
                )
            )

        if not messages:
            messages.append("Coach Miranda Miner: no deep-scan candidates found.")
        return messages

    def maybe_send_telegram_alert(
        self,
        candidate: Candidate,
        thesis: TradeThesis,
        validation: ValidationResult,
        message: str,
    ) -> bool:
        if not self.telegram.configured:
            return False
        if not self._signal_meets_alert_threshold(thesis.signal):
            return False
        if thesis.direction == "none" or thesis.setup.value == "none":
            return False
        if self.journal.alert_sent_recently(
            thesis.symbol,
            thesis.setup.value,
            thesis.signal.value,
            self.settings.alert_cooldown_minutes,
        ):
            return False
        prefix = "Coach Miranda Alert\n"
        if thesis.signal == SignalState.WATCH:
            prefix += "Manual review: setup is forming, not confirmed entry.\n\n"
        if thesis.signal == SignalState.ENTER:
            prefix += "Manual review: entry conditions are confirmed by rules.\n\n"
        try:
            sent = self.telegram.send(prefix + message)
        except requests.RequestException:
            return False
        if sent:
            self.journal.record_alert(
                thesis.symbol,
                thesis.setup.value,
                thesis.signal.value,
                message,
            )
        return sent

    def _signal_meets_alert_threshold(self, signal: SignalState) -> bool:
        thresholds = {
            "enter": {SignalState.ENTER},
            "watch": {SignalState.WATCH, SignalState.ENTER},
            "wait": {SignalState.WATCH, SignalState.ENTER},
        }
        return signal in thresholds.get(self.settings.telegram_min_signal, thresholds["watch"])

    def scan_for_alerts(self) -> str:
        messages = self.scan()
        return "\n\n".join(messages)

    def high_oi_watchlist(
        self,
        limit: int | None = None,
        all_rows: bool = False,
    ) -> tuple[list[OISnapshot], list[str]]:
        if self.settings.coinalyze_api_key and not all_rows:
            rows, warnings = self._dynamic_coinalyze_watchlist()
            if rows:
                row_limit = self.settings.oi_limit if limit is None else limit
                if all_rows:
                    return rows, warnings
                return rows[:row_limit], warnings
        rows, warnings = self.oi_scanner.scan()
        if all_rows:
            return rows, warnings
        row_limit = self.settings.oi_limit if limit is None else limit
        return rows[:row_limit], warnings

    def _dynamic_coinalyze_watchlist(self) -> tuple[list[OISnapshot], list[str]]:
        warnings: list[str] = []
        try:
            candidates = self.discovery.discover(self.settings.prefilter_limit)
        except (CcxtError, requests.RequestException, ValueError) as exc:
            warnings.append(f"Dynamic OI universe unavailable: {exc}")
            return [], warnings
        bases = sorted({candidate.asset.base for candidate in candidates})
        scanner = OpenInterestScanner(self.router, bases, self.settings.coinalyze_api_key)
        rows = scanner.scan_coinalyze_only(warnings)
        return rows, warnings

    def backtest(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str = "miranda",
        side: str = "both",
    ) -> BacktestResult:
        route_symbol = symbol or self.settings.symbol
        route_timeframe = timeframe or self.settings.timeframe
        base = route_symbol.split("/")[0]
        route = self.router.first_available_route(base, self.settings.quote_currency)
        exchange_id = self.settings.exchange_id
        if route is not None:
            exchange_id, route_symbol = route
        candles = self.router.fetch_candles(
            exchange_id,
            route_symbol,
            route_timeframe,
            self.settings.candle_limit,
        )
        if strategy == "miranda":
            allow_longs = side in {"both", "long"}
            allow_shorts = side in {"both", "short"}
            tester = MirandaStrategyBacktester(
                StrategyBacktestConfig(
                    fee_bps=self.settings.backtest_fee_bps,
                    slippage_bps=self.settings.backtest_slippage_bps,
                    stop_atr_multiple=self.settings.backtest_stop_atr_multiple,
                    target_r_multiple=max(
                        self.settings.backtest_target_r_multiple,
                        self.settings.min_risk_reward,
                    ),
                    allow_longs=allow_longs,
                    allow_shorts=allow_shorts,
                    min_risk_reward=self.settings.min_risk_reward,
                )
            )
            return tester.run(route_symbol, route_timeframe, candles)
        return self.backtester.run(route_symbol, route_timeframe, candles)

    def price(self, symbol: str | None = None) -> str:
        route_symbol = symbol or self.settings.symbol
        route = self.router.first_available_route(
            route_symbol.split("/")[0],
            self.settings.quote_currency,
        )
        if route is None:
            return f"No route available for {route_symbol}."
        exchange_id, routed_symbol = route
        try:
            ticker = self.router.fetch_ticker(exchange_id, routed_symbol)
        except (CcxtError, requests.RequestException, ValueError) as exc:
            return (
                f"Could not fetch live price for {routed_symbol} using "
                f"{self.settings.data_mode}: {exc}"
            )
        return (
            f"{routed_symbol} via {self.settings.data_mode}: "
            f"{ticker.last:,.6g} | 24h: {(ticker.percentage or 0):.2f}% | "
            f"volume: {(ticker.quote_volume or 0):,.0f}"
        )

    def doctor(self) -> str:
        free_core = (
            self.settings.discovery_mode == "exchange"
            and self.settings.analyzer_mode == "rule"
        )
        lines = [
            "Coach Miranda Miner Doctor",
            f"Free core: {'yes' if free_core else 'mixed'}",
            f"Data mode: {self.settings.data_mode}",
            f"Discovery mode: {self.settings.discovery_mode}",
            f"Analyzer mode: {self.settings.analyzer_mode}",
            f"Exchange IDs: {', '.join(self.settings.exchange_ids)}",
            f"Telegram configured: {'yes' if self.telegram.configured else 'no'}",
            f"Charts enabled: {'yes' if self.settings.render_charts else 'no'}",
            f"Journal DB: {self.settings.journal_db}",
        ]
        if self.settings.data_mode == "fixture":
            lines.append("Warning: fixture mode uses demo prices; numbers will not update like live markets.")
        if self.settings.data_mode == "live":
            lines.append("Direct exchange mode can fail on hosted servers if the exchange blocks that region.")
        if self.settings.data_mode == "paprika":
            lines.append("Paprika mode uses live prices with local intraday candle scaffolding.")
        if self.settings.data_mode == "coinbase":
            lines.append("Coinbase mode uses real public OHLCV candles without API keys.")
        if self.settings.analyzer_mode == "openai":
            lines.append("OpenAI analyzer is optional and requires OPENAI_API_KEY.")
        return "\n".join(lines)


def _setup_score(
    candidate: Candidate,
    price_change_24h_pct: float | None,
    relative_volume: float | None,
    btc_regime_ok: bool,
) -> SetupScore:
    volume = candidate.volume_24h_usd or 0.0
    oi_change = candidate.open_interest_change_24h_pct
    reasons: list[str] = []

    volume_score = min(max(math.log10(volume) - 6.0, 0.0) * 12.0, 36.0) if volume > 0 else 0.0
    change_score = min(abs(price_change_24h_pct or 0.0) * 1.6, 18.0)
    relvol_score = min(max((relative_volume or 0.0) - 1.0, 0.0) * 18.0, 24.0)
    oi_score = min(abs(oi_change or 0.0) * 1.2, 28.0)
    regime_score = 6.0 if btc_regime_ok else -25.0
    score = max(0.0, volume_score + change_score + relvol_score + oi_score + regime_score)

    if volume:
        reasons.append(f"24h volume supports liquidity at ${volume:,.0f}.")
    if price_change_24h_pct is not None:
        reasons.append(f"24h price move is {price_change_24h_pct:.2f}%.")
    if relative_volume is not None:
        reasons.append(f"15m relative volume is {relative_volume:.2f}x.")
    if oi_change is not None:
        reasons.append(f"Coinalyze 24h OI change is {oi_change:.2f}%.")
    if btc_regime_ok:
        reasons.append("BTC regime allows long setups.")
    else:
        reasons.append("BTC regime blocks aggressive long setups.")

    return SetupScore(
        symbol=candidate.route_symbol,
        rank=0,
        score=round(score, 2),
        volume_24h_usd=candidate.volume_24h_usd,
        price_change_24h_pct=price_change_24h_pct,
        oi_change_24h_pct=oi_change,
        relative_volume=relative_volume,
        btc_regime_ok=btc_regime_ok,
        prefilter_reasons=reasons,
    )


def _elapsed(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 2)
