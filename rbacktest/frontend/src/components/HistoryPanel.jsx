/**
 * 历史面板 —— 回测记录 + Agent 对话记录。
 *
 * Props:
 *   history         - 回测记录数组
 *   showHistory     - 回测历史是否展开
 *   onToggle        - 展开/折叠回调
 *   onRestore       - 恢复回测记录
 *   onDelete        - 删除回测记录
 *   onClear         - 清空回测历史
 *   agentSessions   - Agent 会话列表
 *   showAgentSessions - Agent 会话是否展开
 *   onToggleAgent   - 展开/折叠 Agent 会话
 *   onViewAgent     - 查看某条 Agent 会话
 *   onDeleteAgent   - 删除某条 Agent 会话
 */

import { useState, useEffect } from "react";

export default function HistoryPanel({
  history,
  showHistory,
  onToggle,
  onRestore,
  onDelete,
  onClear,
  agentSessions,
  showAgentSessions,
  onToggleAgent,
  onViewAgent,
  onDeleteAgent,
}) {
  return (
    <>
      {/* 回测历史 */}
      {history.length > 0 && (
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
                      {p.end?.slice(0, 7) || "?"} · {sn.length}策略 · {sc}股
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
      )}

      {/* Agent 对话历史 */}
      {agentSessions && agentSessions.length > 0 && (
        <div className="history-panel">
          <div className="history-header" onClick={onToggleAgent}>
            {showAgentSessions ? "▼" : "▶"} AI 对话历史（
            {agentSessions.length}）
          </div>
          {showAgentSessions && (
            <div className="history-list">
              {agentSessions.map((s) => (
                <div
                  key={s.id}
                  className="history-item"
                  onClick={() => onViewAgent(s)}
                  title={s.saved_at?.slice(0, 19)?.replace("T", " ") || ""}
                >
                  <span className="history-id">{s.id.slice(0, 8)}</span>
                  <span className="history-meta">
                    {s.first_question || "对话"}
                  </span>
                  <button
                    className="history-del"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteAgent(s.id);
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
  );
}
