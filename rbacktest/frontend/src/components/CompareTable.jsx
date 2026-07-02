/**
 * 策略对比表 —— 多策略指标横向对比，最优值高亮。
 *
 * Props:
 *   stratNames  - 策略名字数组
 *   stratMeta   - {[name]: {label, color}}
 *   results     - 回测结果 {[name]: {statistics: {...}}}
 *   metricRows  - 指标行定义 [{key, label, fmt, better}]
 *   show        - 是否展开
 *   onToggle    - 点击标题折叠回调
 */

function bestIndex(values, better) {
  if (better === "higher") {
    let best = -Infinity;
    let idx = -1;
    values.forEach((v, i) => {
      if (v > best) {
        best = v;
        idx = i;
      }
    });
    return idx;
  }
  if (better === "lower") {
    let best = Infinity;
    let idx = -1;
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

export default function CompareTable({
  stratNames,
  stratMeta,
  results,
  metricRows,
  show,
  onToggle,
}) {
  if (stratNames.length === 0) return null;

  return (
    <div className="chart-wrapper">
      <h3 onClick={onToggle} style={{ cursor: "pointer", userSelect: "none" }}>
        {show ? "▼" : "▶"} 策略对比
      </h3>
      {show && (
        <div className="compare-table-wrap">
          <table className="compare-table">
            <thead>
              <tr>
                <th>指标</th>
                {stratNames.map((sn, i) => (
                  <th key={sn}>
                    <span
                      className="strategy-dot"
                      style={{
                        background: stratMeta[sn]?.color || "#333",
                      }}
                    />
                    {stratMeta[sn]?.label || sn}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metricRows.map((row) => {
                const values = stratNames.map(
                  (sn) => results[sn].statistics[row.key],
                );
                const best = bestIndex(values, row.better);
                return (
                  <tr key={row.key}>
                    <td className="metric-label">{row.label}</td>
                    {values.map((v, i) => (
                      <td
                        key={i}
                        className={
                          i === best && stratNames.length > 1 ? "best" : ""
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
  );
}
