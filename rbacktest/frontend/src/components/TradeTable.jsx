/**
 * 交易明细表 —— 逐笔成交展示（日期、标的、方向、价格、盈亏）。
 *
 * Props:
 *   trades     - [{date, symbol, side, price, shares, entry_price, pnl, pnl_pct}]
 *   stockNames - {code: name} 映射
 *   label      - 策略显示名
 *   show       - 是否展开
 *   onToggle   - 点击标题折叠回调
 */

export default function TradeTable({
  trades,
  stockNames,
  label,
  show,
  onToggle,
}) {
  if (!trades || trades.length === 0) return null;

  return (
    <div className="chart-wrapper">
      <h3 onClick={onToggle} style={{ cursor: "pointer", userSelect: "none" }}>
        {show ? "▼" : "▶"} 交易明细 — {label}（{trades.length} 笔）
      </h3>
      {show && (
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
                  <td>{t.date ? String(t.date).slice(0, 10) : "—"}</td>
                  <td>{t.symbol}</td>
                  <td style={{ fontSize: "0.78rem", color: "#888" }}>
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
                    {t.pnl != null ? `¥${Number(t.pnl).toLocaleString()}` : "—"}
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
}
