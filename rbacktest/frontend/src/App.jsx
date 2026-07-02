import { useState, useEffect } from "react";
import ParamPanel from "./components/ParamPanel";
import { MenuIcon, CloseIcon, GripIcon } from "./components/Icons";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";
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
const BENCHMARK_COLOR = "#999999";

const METRIC_ROWS = [
  // 收益类
  {
    key: "total_return",
    label: "总收益率",
    fmt: (v) => `${v.toFixed(2)}%`,
    better: "higher",
  },
  {
    key: "annual_return",
    label: "年化收益率",
    fmt: (v) => `${v.toFixed(2)}%`,
    better: "higher",
  },
  {
    key: "end_balance",
    label: "结束资金",
    fmt: (v) => `¥${Number(v).toLocaleString()}`,
    better: "higher",
  },
  // 风险类
  {
    key: "max_ddpercent",
    label: "最大回撤",
    fmt: (v) => `${v.toFixed(2)}%`,
    better: "lower",
  },
  {
    key: "return_std",
    label: "收益波动率",
    fmt: (v) => `${v.toFixed(2)}%`,
    better: "lower",
  },
  {
    key: "max_drawdown_duration",
    label: "最长回撤(天)",
    fmt: (v) => v,
    better: "lower",
  },
  // 风险调整收益
  {
    key: "sharpe_ratio",
    label: "夏普比率",
    fmt: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "sortino_ratio",
    label: "索提诺比率",
    fmt: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "calmar_ratio",
    label: "卡尔玛比率",
    fmt: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "return_drawdown_ratio",
    label: "收益回撤比",
    fmt: (v) => v.toFixed(2),
    better: "higher",
  },
  // 交易统计
  {
    key: "win_rate",
    label: "胜率",
    fmt: (v) => `${v.toFixed(1)}%`,
    better: "higher",
  },
  {
    key: "profit_factor",
    label: "盈亏比",
    fmt: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "avg_win",
    label: "均盈(%)",
    fmt: (v) => `${v.toFixed(2)}%`,
    better: "higher",
  },
  {
    key: "avg_loss",
    label: "均亏(%)",
    fmt: (v) => `${v.toFixed(2)}%`,
    better: "higher",
  },
  {
    key: "total_trade_count",
    label: "总成交笔数",
    fmt: (v) => v,
    better: "neutral",
  },
  {
    key: "max_consecutive_wins",
    label: "最长连赢",
    fmt: (v) => v,
    better: "higher",
  },
  {
    key: "max_consecutive_losses",
    label: "最长连亏",
    fmt: (v) => v,
    better: "lower",
  },
  // 杂项
  { key: "total_days", label: "总交易日", fmt: (v) => v, better: "neutral" },
  {
    key: "total_commission",
    label: "总手续费",
    fmt: (v) => `¥${Number(v).toFixed(2)}`,
    better: "lower",
  },
];

const CHART_TYPES = [
  { key: "return", label: "收益率曲线" },
  { key: "drawdown", label: "回撤曲线" },
  { key: "capital", label: "资金变化" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function bestIndex(values, better) {
  if (better === "higher") {
    let best = -Infinity,
      idx = -1;
    values.forEach((v, i) => {
      if (v > best) {
        best = v;
        idx = i;
      }
    });
    return idx;
  }
  if (better === "lower") {
    let best = Infinity,
      idx = -1;
    values.forEach((v, i) => {
      if (v < best) {
        best = v;
        idx = i;
      }
    });
    return idx;
  }
  return -1;
}

function mergeMultiSeries(stratResults, fn, capitalRef, stratMeta, benchmark) {
  const allDates = new Set();
  const seriesMap = {};
  const snames = Object.keys(stratResults);

  snames.forEach((sn) => {
    seriesMap[sn] = {};
    (stratResults[sn].daily || []).forEach((d) => {
      allDates.add(d.date);
      seriesMap[sn][d.date] = fn(d, capitalRef);
    });
  });

  // 注入基准数据
  if (benchmark && benchmark.dates) {
    benchmark.dates.forEach((d, i) => {
      allDates.add(d);
      // 基准净值转为与策略相同的尺度
      const benchVal = (benchmark.nav[i] - 1) * 100; // 百分比
      if (!seriesMap["__bench__"]) seriesMap["__bench__"] = {};
      seriesMap["__bench__"][d] = benchVal;
    });
  }

  return [...allDates].sort().map((d) => {
    const row = { date: d };
    snames.forEach((sn) => {
      const label = (stratMeta[sn] && stratMeta[sn].label) || sn;
      row[label] = seriesMap[sn][d] ?? null;
    });
    if (seriesMap["__bench__"]) {
      row["沪深300"] = seriesMap["__bench__"][d] ?? null;
    }
    return row;
  });
}

/* ------------------------------------------------------------------ */
/*  App component                                                     */
/* ------------------------------------------------------------------ */

export default function App() {
  const [results, setResults] = useState(null);
  const [benchmark, setBenchmark] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chartOrder, setChartOrder] = useState([
    "return",
    "drawdown",
    "capital",
  ]);
  const [dragIdx, setDragIdx] = useState(null);
  const [stratMeta, setStratMeta] = useState({});
  const [showTrades, setShowTrades] = useState({});
  const [showCompare, setShowCompare] = useState(true);
  const [stockNames, setStockNames] = useState({});
  // 系统状态
  const [sysStatus, setSysStatus] = useState({ stocks: 0, strats: 0 });
  // 回测历史（localStorage 持久化）
  const [history, setHistory] = useState(() => loadHistory());
  const [showHistory, setShowHistory] = useState(false);

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

  const stratNames = results ? Object.keys(results.results) : [];
  const capitalRef =
    stratNames.length > 0
      ? results.results[stratNames[0]].statistics.capital
      : 1000000;

  function getLabel(sn) {
    return (stratMeta[sn] && stratMeta[sn].label) || sn;
  }
  function getColor(sn, i) {
    return (
      (stratMeta[sn] && stratMeta[sn].color) ||
      DEFAULT_COLORS[i % DEFAULT_COLORS.length]
    );
  }

  // 当回测结果到达时，自动拉取同期基准数据并保存到历史
  const handleResults = async (res, params) => {
    setResults(res);
    setBenchmark(null);

    // 保存到 localStorage
    const entry = {
      task_id: res.task_id,
      params: params || {},
      results: res.results,
      saved_at: new Date().toISOString(),
    };
    saveToHistory(entry);
    setHistory(loadHistory());

    // 从 res 直接取策略名，不用 state（setState 异步，此时 stratNames 还是旧值）
    const names = res ? Object.keys(res.results) : [];
    if (names.length > 0) {
      const daily = res.results[names[0]]?.daily;
      if (daily && daily.length >= 2) {
        const bm = await fetchBenchmark(
          "000300.SSE",
          daily[0].date,
          daily[daily.length - 1].date,
        );
        if (bm && !bm.error) setBenchmark(bm);
      }
    }
  };

  /* ---- drag handlers ---- */
  const handleDragStart = (idx) => setDragIdx(idx);
  const handleDragOver = (e) => e.preventDefault();

  const handleDrop = (targetIdx) => {
    if (dragIdx === null || dragIdx === targetIdx) return;
    const next = [...chartOrder];
    const [moved] = next.splice(dragIdx, 1);
    next.splice(targetIdx, 0, moved);
    setChartOrder(next);
    setDragIdx(null);
  };

  const sortedCharts = chartOrder
    .map((key) => CHART_TYPES.find((c) => c.key === key))
    .filter(Boolean);

  /* ---- inline chart renders ---- */

  const renderReturnChart = () => {
    if (stratNames.length === 0) return null;
    const data = mergeMultiSeries(
      results.results,
      (d) => (d.balance / capitalRef - 1) * 100,
      capitalRef,
      stratMeta,
      benchmark,
    );

    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            formatter={(v, name) => [`${Number(v).toFixed(4)}%`, name]}
          />
          <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
          <Legend />
          {stratNames.map((sn, i) => (
            <Line
              key={sn}
              type="monotone"
              dataKey={getLabel(sn)}
              stroke={getColor(sn, i)}
              strokeWidth={2}
              dot={false}
            />
          ))}
          {benchmark && (
            <Line
              key="bench"
              type="monotone"
              dataKey="沪深300"
              stroke={BENCHMARK_COLOR}
              strokeWidth={1.5}
              strokeDasharray="6 3"
              dot={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const renderDrawdownChart = () => {
    if (stratNames.length === 0) return null;
    // 回撤图不叠加基准——基准 nav 无法直接映射为策略回撤
    const data = mergeMultiSeries(
      results.results,
      (d) => d.ddpercent,
      capitalRef,
      stratMeta,
      null,
    );

    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            domain={["auto", 0]}
          />
          <Tooltip
            formatter={(v, name) => [`${Number(v).toFixed(2)}%`, name]}
          />
          <Legend />
          {stratNames.map((sn, i) => (
            <Line
              key={sn}
              type="monotone"
              dataKey={getLabel(sn)}
              stroke={getColor(sn, i)}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  };

  const renderCapitalChart = () => {
    if (stratNames.length === 0) return null;
    // 资金变化图不叠加基准——基准 nav 与策略绝对金额尺度不同
    const data = mergeMultiSeries(
      results.results,
      (d) => d.balance - capitalRef,
      capitalRef,
      stratMeta,
      null,
    );

    return (
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={40}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `¥${(v / 10000).toFixed(0)}万`}
          />
          <Tooltip
            formatter={(v, name) => [`¥${Number(v).toLocaleString()}`, name]}
          />
          <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
          <Legend />
          {stratNames.map((sn, i) => (
            <Line
              key={sn}
              type="monotone"
              dataKey={getLabel(sn)}
              stroke={getColor(sn, i)}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  };

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
        <h1>量化回测</h1>
        <span className="header-stats">
          {sysStatus.stocks > 0 && (
            <>
              <span className="stat-item">
                {sysStatus.stocks.toLocaleString()} 只股票
              </span>
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
              <ParamPanel onResults={handleResults} />
              {history.length > 0 && (
                <div className="history-panel">
                  <div
                    className="history-header"
                    onClick={() => setShowHistory(!showHistory)}
                  >
                    {showHistory ? "▼" : "▶"} 回测历史（{history.length}）
                    <button
                      className="history-clear"
                      onClick={(e) => {
                        e.stopPropagation();
                        clearHistory();
                        setHistory([]);
                      }}
                      title="清空历史"
                    >
                      ✕
                    </button>
                  </div>
                  {showHistory && (
                    <div className="history-list">
                      {history.map((entry) => (
                        <div
                          key={entry.task_id}
                          className="history-item"
                          onClick={() => {
                            setResults(entry.results);
                            setBenchmark(null);
                          }}
                          title={entry.saved_at.slice(0, 19).replace("T", " ")}
                        >
                          <span className="history-id">
                            {entry.task_id.slice(0, 8)}
                          </span>
                          <span className="history-meta">
                            {entry.params.strategies?.length || 0}策略 ·
                            {entry.params.vt_symbols?.length || 0}股
                          </span>
                          <button
                            className="history-del"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteFromHistory(entry.task_id);
                              setHistory(loadHistory());
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
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
            <div className="results">
              {/* ----- 策略对比表（可折叠）----- */}
              <div className="chart-wrapper">
                <h3
                  onClick={() => setShowCompare(!showCompare)}
                  style={{ cursor: "pointer", userSelect: "none" }}
                >
                  {showCompare ? "▼" : "▶"} 策略对比
                </h3>
                {showCompare && (
                  <div className="compare-table-wrap">
                    <table className="compare-table">
                      <thead>
                        <tr>
                          <th>指标</th>
                          {stratNames.map((sn, i) => (
                            <th key={sn}>
                              <span
                                className="strategy-dot"
                                style={{ background: getColor(sn, i) }}
                              />
                              {getLabel(sn)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {METRIC_ROWS.map((row) => {
                          const values = stratNames.map(
                            (sn) => results.results[sn].statistics[row.key],
                          );
                          const best = bestIndex(values, row.better);
                          return (
                            <tr key={row.key}>
                              <td className="metric-label">{row.label}</td>
                              {values.map((v, i) => (
                                <td
                                  key={i}
                                  className={
                                    i === best && stratNames.length > 1
                                      ? "best"
                                      : ""
                                  }
                                >
                                  {v != null ? row.fmt(v) : "—"}
                                </td>
                              ))}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* ----- 交易明细表 ----- */}
              {stratNames.map((sn) => {
                const trades = results.results[sn].trades || [];
                if (trades.length === 0) return null;
                return (
                  <div className="chart-wrapper" key={`trades-${sn}`}>
                    <h3
                      onClick={() =>
                        setShowTrades((prev) => ({ ...prev, [sn]: !prev[sn] }))
                      }
                      style={{ cursor: "pointer", userSelect: "none" }}
                    >
                      {showTrades[sn] ? "▼" : "▶"} 交易明细 — {getLabel(sn)}（
                      {trades.length} 笔）
                    </h3>
                    {showTrades[sn] && (
                      <div
                        className="compare-table-wrap"
                        style={{ maxHeight: 400, overflowY: "auto" }}
                      >
                        <table className="compare-table">
                          <thead>
                            <tr>
                              <th>日期</th>
                              <th>标的</th>
                              <th>名称</th>
                              <th>方向</th>
                              <th>成交价</th>
                              <th>股数</th>
                              <th>成本价</th>
                              <th>盈亏</th>
                              <th>盈亏%</th>
                            </tr>
                          </thead>
                          <tbody>
                            {trades.map((t, i) => (
                              <tr key={i}>
                                <td>
                                  {t.date ? String(t.date).slice(0, 10) : "—"}
                                </td>
                                <td>{t.symbol}</td>
                                <td
                                  style={{ fontSize: "0.78rem", color: "#888" }}
                                >
                                  {stockNames[t.symbol] || ""}
                                </td>
                                <td>{t.side}</td>
                                <td>¥{Number(t.price).toFixed(2)}</td>
                                <td>{Number(t.shares).toLocaleString()}</td>
                                <td>
                                  {t.entry_price != null
                                    ? `¥${Number(t.entry_price).toFixed(2)}`
                                    : "—"}
                                </td>
                                <td
                                  style={{
                                    color:
                                      t.pnl > 0
                                        ? "#cf1322"
                                        : t.pnl < 0
                                          ? "#389e0d"
                                          : undefined,
                                  }}
                                >
                                  {t.pnl != null
                                    ? `¥${Number(t.pnl).toLocaleString()}`
                                    : "—"}
                                </td>
                                <td
                                  style={{
                                    color:
                                      t.pnl_pct > 0
                                        ? "#cf1322"
                                        : t.pnl_pct < 0
                                          ? "#389e0d"
                                          : undefined,
                                  }}
                                >
                                  {t.pnl_pct != null
                                    ? `${Number(t.pnl_pct).toFixed(2)}%`
                                    : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="chart-sort-bar">
                <span className="sort-hint">
                  拖动图表可调整顺序 ｜ 灰色虚线 = 沪深300基准
                </span>
                <button
                  className="export-btn"
                  onClick={async () => {
                    const res = await fetch("/api/export", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ results: results.results }),
                    });
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "backtest_results.csv";
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  导出 CSV
                </button>
              </div>

              {/* ----- draggable charts ----- */}
              {sortedCharts.map(({ key, label }, idx) => (
                <div
                  key={key}
                  className={`chart-slot ${dragIdx === idx ? "dragging" : ""}`}
                  draggable
                  onDragStart={() => handleDragStart(idx)}
                  onDragOver={handleDragOver}
                  onDrop={() => handleDrop(idx)}
                  onDragEnd={() => setDragIdx(null)}
                >
                  <div className="chart-handle" title="拖动排序">
                    <GripIcon /> {label}
                  </div>
                  <div className="chart-wrapper">
                    {key === "return" && renderReturnChart()}
                    {key === "drawdown" && renderDrawdownChart()}
                    {key === "capital" && renderCapitalChart()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
