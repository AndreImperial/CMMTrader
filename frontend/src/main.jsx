import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  Gauge,
  HeartPulse,
  LineChart,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";

const nav = [
  ["Overview", Gauge],
  ["Market Scanner", Activity],
  ["Scalper", Zap],
  ["Open Interest", BarChart3],
  ["Backtests", LineChart],
  ["Journal", BookOpen],
  ["System Health", HeartPulse],
];

const fallbackSpark = [
  { label: "Mon", value: 31 },
  { label: "Tue", value: 48 },
  { label: "Wed", value: 42 },
  { label: "Thu", value: 62 },
  { label: "Fri", value: 58 },
  { label: "Sat", value: 77 },
  { label: "Sun", value: 69 },
];

function App() {
  const [view, setView] = useState("Overview");
  const [overview, setOverview] = useState(null);
  const [scan, setScan] = useState(null);
  const [scalp, setScalp] = useState(null);
  const [oi, setOi] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [journal, setJournal] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    loadOverview();
  }, []);

  async function request(path, options = {}) {
    setError("");
    const response = await fetch(path, options);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Request failed: ${response.status}`);
    }
    return response.json();
  }

  async function loadOverview() {
    setBusy("overview");
    try {
      setOverview(await request("/api/overview"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function runScan() {
    setBusy("scan");
    try {
      const payload = await request("/api/scan", { method: "POST" });
      setScan(payload);
      setView("Market Scanner");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function runScalp() {
    setBusy("scalp");
    try {
      setScalp(await request("/api/scalp", { method: "POST" }));
      setView("Scalper");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function runOi() {
    setBusy("oi");
    try {
      setOi(await request("/api/open-interest"));
      setView("Open Interest");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function runBacktest() {
    setBusy("backtest");
    try {
      setBacktest(await request("/api/backtest", { method: "POST" }));
      setView("Backtests");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function loadJournal() {
    setBusy("journal");
    try {
      setJournal(await request("/api/journal"));
      setView("Journal");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  const health = overview?.health;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">CM</div>
          <div>
            <div className="brand-name">CMMTrader</div>
            <div className="brand-caption">Paper ops console</div>
          </div>
        </div>

        <nav className="nav-list" aria-label="Primary">
          {nav.map(([label, Icon]) => (
            <button
              className={`nav-item ${view === label ? "active" : ""}`}
              key={label}
              onClick={() => setView(label)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="side-panel">
          <div className="panel-kicker">Execution</div>
          <div className="paper-pill">
            <ShieldCheck size={16} />
            Paper only
          </div>
          <p>Live order placement remains disabled. Signals are for manual review.</p>
        </div>
      </aside>

      <main className="workspace">
        <header className="hero">
          <div>
            <div className="eyebrow">
              <Sparkles size={16} />
              Institutional scanner workspace
            </div>
            <h1>Trade setup intelligence without the dashboard noise.</h1>
            <p>
              Monitor market regime, scan ranked setups, review evidence, and keep
              paper-mode risk controls visible at every step.
            </p>
          </div>
          <div className="hero-actions">
            <button className="primary-action" onClick={runScan} disabled={busy === "scan"}>
              {busy === "scan" ? <RefreshCw className="spin" size={18} /> : <Play size={18} />}
              Run scanner
            </button>
            <button className="ghost-action" onClick={loadOverview}>
              <RefreshCw size={18} />
              Refresh health
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={18} />
            {error}
          </div>
        )}

        <StatusStrip health={health} overview={overview} />

        <section className="content-panel">
          {view === "Overview" && (
            <Overview
              overview={overview}
              scan={scan}
              onScan={runScan}
              onScalp={runScalp}
              onOi={runOi}
              onBacktest={runBacktest}
              busy={busy}
            />
          )}
          {view === "Market Scanner" && <MarketScanner scan={scan} onScan={runScan} busy={busy} />}
          {view === "Scalper" && <Scalper scalp={scalp} onScalp={runScalp} busy={busy} />}
          {view === "Open Interest" && <OpenInterest oi={oi} onOi={runOi} busy={busy} />}
          {view === "Backtests" && (
            <Backtests backtest={backtest} onBacktest={runBacktest} busy={busy} />
          )}
          {view === "Journal" && (
            <Journal journal={journal} onLoad={loadJournal} busy={busy} />
          )}
          {view === "System Health" && <SystemHealth overview={overview} onRefresh={loadOverview} />}
        </section>
      </main>
    </div>
  );
}

function StatusStrip({ health, overview }) {
  const guardrails = overview?.guardrails;
  return (
    <section className="status-grid">
      <Metric label="Mode" value={health?.tradingMode?.toUpperCase() || "PAPER"} tone="good" />
      <Metric label="Data Source" value={health?.dataMode || "loading"} />
      <Metric label="Telegram" value={health?.telegramConfigured ? "On" : "Off"} />
      <Metric label="Coinalyze" value={health?.coinalyzeConfigured ? "On" : "Off"} />
      <Metric
        label="Min R/R"
        value={guardrails ? guardrails.minRiskReward.toFixed(1) : "2.0"}
      />
    </section>
  );
}

function Overview({ overview, scan, onScan, onScalp, onOi, onBacktest, busy }) {
  const guardrails = overview?.guardrails || {};
  return (
    <div className="view-stack">
      <div className="section-heading">
        <div>
          <span className="panel-kicker">Overview</span>
          <h2>Operating cockpit</h2>
        </div>
        <div className="button-row">
          <button onClick={onScan} className="primary-action compact" disabled={busy === "scan"}>
            Run scan
          </button>
          <button onClick={onScalp} className="ghost-action compact" disabled={busy === "scalp"}>
            Scalp
          </button>
          <button onClick={onOi} className="ghost-action compact" disabled={busy === "oi"}>
            OI
          </button>
          <button onClick={onBacktest} className="ghost-action compact" disabled={busy === "backtest"}>
            Backtest
          </button>
        </div>
      </div>
      <div className="ops-grid">
        <InfoCard title="Max position" value={money(guardrails.maxPositionUsd)} note="Per trade cap" />
        <InfoCard title="Daily loss cap" value={money(guardrails.maxDailyLossUsd)} note="Paper guardrail" />
        <InfoCard title="BTC kill switch" value={`${guardrails.btcKillSwitchDropPct ?? 3}%`} note="Regime gate" />
        <InfoCard title="Min volume" value={compactMoney(guardrails.minVolume24hUsd)} note="Liquidity floor" />
      </div>
      <div className="split-layout">
        <div className="chart-card">
          <div className="card-title">Signal throughput</div>
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart data={fallbackSpark}>
              <defs>
                <linearGradient id="throughput" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#71e6ff" stopOpacity={0.5} />
                  <stop offset="95%" stopColor="#71e6ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,.06)" vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis hide />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="value" stroke="#71e6ff" fill="url(#throughput)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="activity-card">
          <div className="card-title">Latest scanner state</div>
          <SignalSummary scan={scan} />
        </div>
      </div>
    </div>
  );
}

function MarketScanner({ scan, onScan, busy }) {
  const results = scan?.results || [];
  return (
    <div className="view-stack">
      <ActionHeader
        kicker="Market scanner"
        title="Ranked intraday setups"
        action="Run market scan"
        onAction={onScan}
        busy={busy === "scan"}
      />
      {!scan ? <EmptyState text="Run a scan to populate ranked setups." /> : <ScanResults results={results} />}
    </div>
  );
}

function ScanResults({ results }) {
  return (
    <>
      <div className="signal-grid">
        {results.slice(0, 8).map((item) => (
          <SignalCard key={`${item.rank}-${item.symbol}`} item={item} />
        ))}
      </div>
      <DataTable
        rows={results}
        columns={["rank", "symbol", "signal", "direction", "setup", "grade", "confidence", "riskReward"]}
      />
    </>
  );
}

function Scalper({ scalp, onScalp, busy }) {
  return (
    <div className="view-stack">
      <ActionHeader
        kicker="Scalper"
        title="3m execution candidates"
        action="Run scalp scan"
        onAction={onScalp}
        busy={busy === "scalp"}
      />
      {!scalp ? (
        <EmptyState text="Run the scalp scanner to load execution-timeframe setups." />
      ) : (
        <DataTable rows={scalp.results || []} columns={["symbol", "signal", "direction", "grade", "confidence", "entry", "score"]} />
      )}
    </div>
  );
}

function OpenInterest({ oi, onOi, busy }) {
  return (
    <div className="view-stack">
      <ActionHeader
        kicker="Open interest"
        title="Derivatives and volume context"
        action="Refresh OI"
        onAction={onOi}
        busy={busy === "oi"}
      />
      {!oi ? (
        <EmptyState text="Refresh open interest to load derivatives context." />
      ) : (
        <DataTable rows={oi.rows || []} columns={["symbol", "source", "status", "open_interest_change_24h_pct", "volume_24h_usd"]} />
      )}
    </div>
  );
}

function Backtests({ backtest, onBacktest, busy }) {
  return (
    <div className="view-stack">
      <ActionHeader
        kicker="Backtests"
        title="Research-grade validation"
        action="Run BTC backtest"
        onAction={onBacktest}
        busy={busy === "backtest"}
      />
      {!backtest ? (
        <EmptyState text="Run a backtest to review assumptions and warnings." />
      ) : (
        <div className="backtest-output">{backtest.formatted}</div>
      )}
    </div>
  );
}

function Journal({ journal, onLoad, busy }) {
  return (
    <div className="view-stack">
      <ActionHeader
        kicker="Journal"
        title="Signal and alert history"
        action="Load journal"
        onAction={onLoad}
        busy={busy === "journal"}
      />
      {!journal ? (
        <EmptyState text="Load the journal to inspect recent setups, alerts, and outcomes." />
      ) : (
        <DataTable rows={journal.theses || []} columns={["created_at", "symbol", "setup", "signal", "confidence", "approved"]} />
      )}
    </div>
  );
}

function SystemHealth({ overview, onRefresh }) {
  return (
    <div className="view-stack">
      <ActionHeader
        kicker="System health"
        title="Runtime configuration"
        action="Refresh"
        onAction={onRefresh}
      />
      <div className="doctor-list">
        {(overview?.doctor || []).map((line) => (
          <div className={line.startsWith("Warning:") ? "doctor-warning" : "doctor-line"} key={line}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

function ActionHeader({ kicker, title, action, onAction, busy }) {
  return (
    <div className="section-heading">
      <div>
        <span className="panel-kicker">{kicker}</span>
        <h2>{title}</h2>
      </div>
      <button className="primary-action compact" onClick={onAction} disabled={busy}>
        {busy ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
        {action}
      </button>
    </div>
  );
}

function SignalCard({ item }) {
  return (
    <article className={`signal-card ${item.signal}`}>
      <div className="signal-top">
        <div>
          <div className="symbol">{item.symbol}</div>
          <div className="setup">{item.setup} · {item.direction}</div>
        </div>
        <span className={`signal-pill ${item.signal}`}>{item.signal}</span>
      </div>
      <div className="signal-metrics">
        <Mini label="Entry" value={price(item.entry)} />
        <Mini label="Stop" value={price(item.stopLoss)} />
        <Mini label="Target" value={price(item.targets?.[0])} />
        <Mini label="R/R" value={item.riskReward?.toFixed?.(2) || "n/a"} />
      </div>
      <div className="evidence-line">{item.prefilterReasons?.[0] || item.validationReasons?.[0] || "Awaiting evidence details."}</div>
    </article>
  );
}

function SignalSummary({ scan }) {
  if (!scan) return <EmptyState text="No scan has run in this browser session." compact />;
  const summary = scan.summary;
  return (
    <div className="summary-list">
      <Mini label="Candidates" value={summary.candidates_scanned} />
      <Mini label="Deep analyzed" value={summary.deep_analyzed} />
      <Mini label="Failed" value={summary.failed_symbols} />
      <Mini label="Duration" value={`${(summary.duration_seconds || 0).toFixed(1)}s`} />
    </div>
  );
}

function Metric({ label, value, tone }) {
  return (
    <div className={`metric-card ${tone || ""}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}

function InfoCard({ title, value, note }) {
  return (
    <div className="info-card">
      <div className="metric-label">{title}</div>
      <div className="info-value">{value || "n/a"}</div>
      <div className="note">{note}</div>
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="mini">
      <span>{label}</span>
      <strong>{value ?? "n/a"}</strong>
    </div>
  );
}

function EmptyState({ text, compact }) {
  return (
    <div className={`empty-state ${compact ? "compact" : ""}`}>
      <TerminalSquare size={compact ? 18 : 28} />
      <span>{text}</span>
    </div>
  );
}

function DataTable({ rows, columns }) {
  if (!rows?.length) return <EmptyState text="No rows available yet." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{labelize(column)}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, 80).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function labelize(value) {
  return value.replaceAll("_", " ").replace(/([A-Z])/g, " $1");
}

function formatCell(value) {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return Math.abs(value) > 999 ? value.toLocaleString() : value.toFixed(2);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function money(value) {
  if (!value && value !== 0) return "n/a";
  return `$${Number(value).toLocaleString()}`;
}

function compactMoney(value) {
  if (!value && value !== 0) return "n/a";
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  return money(value);
}

function price(value) {
  if (!value && value !== 0) return "n/a";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 6 });
}

const tooltipStyle = {
  background: "#111923",
  border: "1px solid rgba(255,255,255,.12)",
  borderRadius: 8,
  color: "#eef4f8",
};

createRoot(document.getElementById("root")).render(<App />);
