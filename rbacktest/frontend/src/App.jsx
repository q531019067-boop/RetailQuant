import { useState, useEffect, useRef, useCallback } from "react";
import ParamPanel from "./components/ParamPanel";
import CompareTable from "./components/CompareTable";
import TradeTable from "./components/TradeTable";
import ChartPanel from "./components/ChartPanel";
import HistoryPanel from "./components/HistoryPanel";
import AgentButton from "./components/AgentButton";
import AgentPanel from "./components/AgentPanel";
import { MenuIcon, CloseIcon } from "./components/Icons";
import {
  fetchStrategies,
  fetchBenchmark,
  fetchStockNames,
  saveToHistory,
  loadHistory,
  deleteFromHistory,
  clearHistory,
} from "./api";
import "./App.css";

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const DEFAULT_COLORS = ["#cf1322", "#1890ff", "#722ed1", "#eb2f96", "#fa8c16"];

const METRIC_ROWS = [
  { key: "total_return", label: "总收益率", fmt: (v) => `${v.toFixed(2)}%`, better: "higher" },
  { key: "annual_return", label: "年化收益率", fmt: (v) => `${v.toFixed(2)}%`, better: "higher" },
  { key: "end_balance", label: "结束资金", fmt: (v) => `¥${Number(v).toLocaleString()}`, better: "higher" },
  { key: "max_ddpercent", label: "最大回撤", fmt: (v) => `${v.toFixed(2)}%`, better: "lower" },
  { key: "return_std", label: "收益波动率", fmt: (v) => `${v.toFixed(2)}%`, better: "lower" },
  { key: "max_drawdown_duration", label: "最长回撤(天)", fmt: (v) => v, better: "lower" },
  { key: "sharpe_ratio", label: "夏普比率", fmt: (v) => v.toFixed(2), better: "higher" },
  { key: "sortino_ratio", label: "索提诺比率", fmt: (v) => v.toFixed(2), better: "higher" },
  { key: "calmar_ratio", label: "卡尔玛比率", fmt: (v) => v.toFixed(2), better: "higher" },
  { key: "return_drawdown_ratio", label: "收益回撤比", fmt: (v) => v.toFixed(2), better: "higher" },
  { key: "win_rate", label: "胜率", fmt: (v) => `${v.toFixed(1)}%`, better: "higher" },
  { key: "profit_factor", label: "盈亏比", fmt: (v) => v.toFixed(2), better: "higher" },
  { key: "avg_win", label: "均盈(%)", fmt: (v) => `${v.toFixed(2)}%`, better: "higher" },
  { key: "avg_loss", label: "均亏(%)", fmt: (v) => `${v.toFixed(2)}%`, better: "higher" },
  { key: "total_trade_count", label: "总成交笔数", fmt: (v) => v, better: "neutral" },
  { key: "max_consecutive_wins", label: "最长连赢", fmt: (v) => v, better: "higher" },
  { key: "max_consecutive_losses", label: "最长连亏", fmt: (v) => v, better: "lower" },
  { key: "total_days", label: "总交易日", fmt: (v) => v, better: "neutral" },
  { key: "total_commission", label: "总手续费", fmt: (v) => `¥${Number(v).toFixed(2)}`, better: "lower" },
];

/* ------------------------------------------------------------------ */
/*  App component                                                     */
/* ------------------------------------------------------------------ */

export default function App() {
  const [results, setResults] = useState(null);
  const [benchmark, setBenchmark] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [stratMeta, setStratMeta] = useState({});
  const [showTrades, setShowTrades] = useState({});
  const [showCompare, setShowCompare] = useState(true);
  const [stockNames, setStockNames] = useState({});
  const [sysStatus, setSysStatus] = useState({ stocks: 0, strats: 0 });

  // 回测历史
  const [history, setHistory] = useState(() => loadHistory());
  const [showHistory, setShowHistory] = useState(false);
  const [restoredParams, setRestoredParams] = useState(null);

  // 最近一次回测参数（供 Agent 使用）
  const [lastParams, setLastParams] = useState(null);

  // Agent 状态
  const [agentOpen, setAgentOpen] = useState(false);
  const [resultVersion, setResultVersion] = useState(0);
  const resultVersionRef = useRef(0);
  useEffect(() => { resultVersionRef.current = resultVersion; }, [resultVersion]);

  /* ---- initial data fetch ---- */

  useEffect(() => {
    Promise.all([
      fetchStrategies(),
      fetch("/api/stocks").then((r) => r.json()),
      fetchStockNames(),
    ]).then(([strats, stockData, nameData]) => {
      const meta = {};
      strats.forEach((s, i) => {
        meta[s.name] = {
          label: s.label,
          color: s.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
        };
      });
      setStratMeta(meta);
      setStockNames(nameData.names || {});
      setSysStatus({
        stocks: stockData.stocks?.length || 0,
        strats: strats.length || 0,
      });
    });
  }, []);

  /* ---- backtest result handler ---- */

  const handleResults = async (res, params) => {
    setResults(res);
    setBenchmark(null);
    setLastParams(params || null);
    setResultVersion((v) => v + 1);

    const entry = {
      task_id: res.task_id,
      params: params || {},
      results: res,
      saved_at: new Date().toISOString(),
    };
    saveToHistory(entry);
    setHistory(loadHistory());

    const names = res ? Object.keys(res.results) : [];
    if (names.length > 0) {
      const daily = res.results[names[0]]?.daily;
      if (daily && daily.length >= 2) {
        const bm = await fetchBenchmark("000300.SSE", daily[0].date, daily[daily.length - 1].date);
        if (bm && !bm.error) setBenchmark(bm);
      }
    }
  };

  /* ---- history handlers ---- */

  const handleRestoreHistory = (entry) => {
    setResults(entry.results);
    setBenchmark(null);
    setRestoredParams(entry.params);
    setResultVersion((v) => v + 1);
  };

  const handleDeleteHistory = (taskId) => {
    deleteFromHistory(taskId);
    setHistory(loadHistory());
  };

  const handleClearHistory = () => {
    clearHistory();
    setHistory([]);
  };

  /* ---- Agent handlers ---- */

  const handleAgentViewResults = useCallback((data) => {
    const cv = resultVersionRef.current;
    setResultVersion((v) => v + 1);
    if (cv > 0) {
      const ok = window.confirm("Agent 查看图表将覆盖当前的图表和数据。\n确定要切换吗？");
      if (!ok) return;
    }
    setResults(data);
    setBenchmark(null);
  }, []);

  /* ---- derived ---- */

  const stratNames = results ? Object.keys(results.results) : [];
  function getLabel(sn) { return (stratMeta[sn] && stratMeta[sn].label) || sn; }

  /* ---- render ---- */

  return (
    <div className="app">
      <header className="app-header">
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          title={sidebarCollapsed ? "展开参数面板" : "收起参数面板"}
        >
          {sidebarCollapsed ? <MenuIcon /> : <CloseIcon />}
        </button>
        <h1>Rbacktest</h1>
        <span className="header-stats">
          {sysStatus.stocks > 0 && (
            <>
              <span className="stat-item">{sysStatus.stocks.toLocaleString()} 只股票</span>
              <span className="stat-divider">·</span>
              <span className="stat-item">{sysStatus.strats} 个策略</span>
            </>
          )}
        </span>
      </header>

      <main className="app-main">
        <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
          {!sidebarCollapsed && (
            <>
              <ParamPanel onResults={handleResults} restoredParams={restoredParams} />
              <HistoryPanel
                history={history}
                showHistory={showHistory}
                onToggle={() => setShowHistory(!showHistory)}
                onRestore={handleRestoreHistory}
                onDelete={handleDeleteHistory}
                onClear={handleClearHistory}
              />
            </>
          )}
        </aside>

        <section className="content">
          {!results && (
            <div className="placeholder">
              <p>请在左侧选择回测参数，然后点击运行回测</p>
            </div>
          )}

          {results && stratNames.length > 0 && (
            <>
              <CompareTable
                stratNames={stratNames}
                stratMeta={stratMeta}
                results={results.results}
                metricRows={METRIC_ROWS}
                show={showCompare}
                onToggle={() => setShowCompare(!showCompare)}
              />

              {stratNames.map((sn) => (
                <TradeTable
                  key={`trades-${sn}`}
                  trades={results.results[sn].trades || []}
                  stockNames={stockNames}
                  label={getLabel(sn)}
                  show={showTrades[sn] || false}
                  onToggle={() => setShowTrades((prev) => ({ ...prev, [sn]: !prev[sn] }))}
                />
              ))}

              <ChartPanel results={results} benchmark={benchmark} stratMeta={stratMeta} />
            </>
          )}
        </section>
      </main>

      {/* Agent 浮动按钮 */}
      <AgentButton onToggle={() => setAgentOpen((p) => !p)} />

      {/* Agent 对话面板 */}
      {agentOpen && (
        <AgentPanel
          results={results}
          params={lastParams}
          onClose={() => setAgentOpen(false)}
          onViewResults={handleAgentViewResults}
        />
      )}
    </div>
  );
}
