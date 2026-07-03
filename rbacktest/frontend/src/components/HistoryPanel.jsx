/**
 * 回测历史面板 —— localStorage 持久化的回测记录列表。
 *
 * Props:
 *   history      - 历史记录数组
 *   showHistory  - 是否展开
 *   onToggle     - 展开/折叠回调
 *   onRestore    - 恢复某条记录的回调 (entry) => void
 *   onDelete     - 删除某条记录的回调 (task_id) => void
 *   onClear      - 清空全部记录的回调
 */

export default function HistoryPanel({
  history,
  showHistory,
  onToggle,
  onRestore,
  onDelete,
  onClear,
}) {
  if (history.length === 0) return null;

  return (
    <div className="history-panel">
      <div className="history-header" onClick={onToggle}>
        {showHistory ? "▼" : "▶"} 回测历史（{history.length}）
        <button
          className="history-clear"
          onClick={(e) => {
            e.stopPropagation();
            onClear();
          }}
          title="清空历史"
        >
          ✕
        </button>
      </div>
      {showHistory && (
        <div className="history-list">
          {history.map((entry) => {
            const p = entry.params || {};
            const sn = p.strategies || [];
            const sc = p.vt_symbols?.length || 0;
            const tip = [
              entry.saved_at.slice(0, 19).replace("T", " "),
              `区间: ${p.start || "?"} ~ ${p.end || "?"}`,
              `资金: ¥${(p.capital || 0).toLocaleString()}`,
              `策略: ${sn.join(", ") || "?"}`,
              `股票: ${sc} 只`,
            ].join("\n");
            return (
              <div
                key={entry.task_id}
                className="history-item"
                onClick={() => onRestore(entry)}
                title={tip}
              >
                <span className="history-id">
                  {entry.task_id.slice(0, 8)}
                </span>
                <span className="history-meta">
                  {p.start?.slice(0, 7) || "?"} ~{" "}
                  {p.end?.slice(0, 7) || "?"} · {sn.length}策略 ·{" "}
                  {sc}股
                </span>
                <button
                  className="history-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(entry.task_id);
                  }}
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
