/**
 * 图表面板 —— 管理图表排序、拖拽、渲染。
 *
 * Props:
 *   results       - 回测结果 {results: {strat: {statistics, daily, trades}}}
 *   benchmark     - 基准数据 {dates, nav}
 *   stratMeta     - 策略元数据 {name: {label, color}}
 *   stockNames    - 股票名称映射
 */

import { useState, useCallback } from "react";
import { GripIcon } from "./Icons";
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

const DEFAULT_COLORS = ["#cf1322", "#1890ff", "#722ed1", "#eb2f96", "#fa8c16"];
const BENCHMARK_COLOR = "#999999";

const CHART_TYPES = [
  { key: "return", label: "收益率曲线" },
  { key: "drawdown", label: "回撤曲线" },
  { key: "capital", label: "资金变化" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

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

  if (benchmark && benchmark.dates) {
    benchmark.dates.forEach((d, i) => {
      allDates.add(d);
      const benchVal = (benchmark.nav[i] - 1) * 100;
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
/*  Component                                                         */
/* ------------------------------------------------------------------ */

export default function ChartPanel({ results, benchmark, stratMeta }) {
  const [chartOrder, setChartOrder] = useState([
    "return",
    "drawdown",
    "capital",
  ]);
  const [dragIdx, setDragIdx] = useState(null);

  const handleDragStart = useCallback((idx) => setDragIdx(idx), []);
  const handleDragOver = useCallback((e) => e.preventDefault(), []);

  const handleDrop = useCallback(
    (targetIdx) => {
      if (dragIdx === null || dragIdx === targetIdx) return;
      const next = [...chartOrder];
      const [moved] = next.splice(dragIdx, 1);
      next.splice(targetIdx, 0, moved);
      setChartOrder(next);
      setDragIdx(null);
    },
    [dragIdx, chartOrder],
  );

  const sortedCharts = chartOrder
    .map((key) => CHART_TYPES.find((c) => c.key === key))
    .filter(Boolean);

  if (!results) return null;

  const stratNames = Object.keys(results.results);
  if (stratNames.length === 0) return null;

  const capitalRef =
    results.results[stratNames[0]].statistics.capital || 1_000_000;

  function getLabel(sn) {
    return (stratMeta[sn] && stratMeta[sn].label) || sn;
  }
  function getColor(sn, i) {
    return (
      (stratMeta[sn] && stratMeta[sn].color) ||
      DEFAULT_COLORS[i % DEFAULT_COLORS.length]
    );
  }

  /* ---- chart renders ---- */

  const renderReturnChart = () => {
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
    <div className="results">
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
  );
}
