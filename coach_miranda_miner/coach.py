from __future__ import annotations

from ccxt import NetworkError
import requests

from .alerts import AlertFormatter
from .analyzer import OpenAIVisionAnalyzer, RuleBasedAnalyzer
from .backtest import BacktestResult, MovingAverageBacktester
from .broker import PaperBroker
from .charts import ChartRenderer
from .config import Settings
from .data import MarketData
from .discovery import DEFAULT_MAJORS, DiscoveryEngine, ExchangeMomentumDiscoveryEngine
from .exchanges import (
    CoinGeckoRouter,
    CoinPaprikaRouter,
    ExchangeRouter,
    FixtureExchangeRouter,
    YahooFinanceRouter,
)
from .gatekeepers import Gatekeeper
from .intelligence import IntelligenceGatherer
from .journal import Journal
from .market_cap import CoinMarketCapProvider, StaticMarketCapProvider
from .miner import SignalMiner
from .news import CryptoPanicNewsProvider, EmptyNewsProvider
from .risk import RiskManager
from .telegram import TelegramAlerter
from .validator import ThesisValidator


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
            else ExchangeRouter(settings.exchange_ids)
        )
        self.discovery = self._build_discovery()
        self.gatekeeper = Gatekeeper(
            self.router,
            settings.btc_kill_switch_drop_pct,
            settings.min_volume_24h_usd,
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
        try:
            market_regime = self.gatekeeper.market_regime()
            candidates = self.discovery.discover(self.settings.discovery_limit)
        except (NetworkError, requests.RequestException, ValueError) as exc:
            return [
                "Live data is not available right now.",
                f"Data mode: {self.settings.data_mode}",
                f"Reason: {exc}",
                "Try again in a few minutes, or use DATA_MODE=fixture for offline demo mode.",
            ]
        messages: list[str] = []

        if self.settings.data_mode == "fixture":
            messages.append(
                "DEMO DATA MODE: prices are synthetic and repeatable. "
                "Use DATA_MODE=live for updating exchange prices."
            )

        for candidate in candidates:
            passed, gate_reasons = self.gatekeeper.filter_candidate(candidate)
            if not passed:
                messages.append(
                    f"{candidate.route_symbol}: skipped by gatekeepers: "
                    f"{'; '.join(gate_reasons)}"
                )
                continue

            pack = self.intelligence.gather(candidate, market_regime)
            thesis = self.analyzer.analyze(pack)
            atr = next(
                (item.atr for item in pack.indicators if item.timeframe == "15m"),
                None,
            )
            validation = self.validator.validate(thesis, market_regime, atr)
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
            message = self.alerts.format(candidate, thesis, validation)
            self.telegram.send(message)
            messages.append(message)

        if not messages:
            messages.append("Coach Miranda Miner: no routed candidates found.")
        return messages

    def backtest(self, symbol: str | None = None, timeframe: str | None = None) -> BacktestResult:
        route_symbol = symbol or self.settings.symbol
        route_timeframe = timeframe or self.settings.timeframe
        candles = self.router.fetch_candles(
            self.settings.exchange_id,
            route_symbol,
            route_timeframe,
            self.settings.candle_limit,
        )
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
        except (NetworkError, requests.RequestException, ValueError) as exc:
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
            lines.append("Live public exchange data requires working internet/DNS.")
        if self.settings.data_mode == "paprika":
            lines.append("Paprika mode uses live prices with local intraday candle scaffolding.")
        if self.settings.analyzer_mode == "openai":
            lines.append("OpenAI analyzer is optional and requires OPENAI_API_KEY.")
        return "\n".join(lines)
