/**
 * Agent 对话面板 —— 右侧滑入，不阻塞主界面。
 *
 * 改进：
 * - 无遮罩层，主界面始终可操作
 * - 可最小化为侧边标签
 * - 缓存 tool 返回的回测结果，点击「查看图表」注入主视图
 */

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function IconMaximize({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="4" y="4" width="16" height="16" rx="2" />
    </svg>
  );
}

function IconRestore({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="10" y="2" width="12" height="12" rx="2" />
      <rect x="2" y="10" width="12" height="12" rx="2" />
    </svg>
  );
}

const ACTION_LABELS = {
  analyze: "分析回测",
  optimize: "优化参数",
  risk: "风险诊断",
  explore: "批量探索",
};

export default function AgentPanel({
  action,
  results,
  params,
  onClose,
  onViewResults,
}) {
  const [events, setEvents] = useState([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);
  const [followUp, setFollowUp] = useState("");
  const [loading, setLoading] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [cachedResults, setCachedResults] = useState({});
  const [sessionId, setSessionId] = useState(null);
  const cacheIdRef = useRef(0);
  const bottomRef = useRef(null);
  const abortRef = useRef(null);

  const label = ACTION_LABELS[action] || action;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const startSession = useCallback(
    async (question) => {
      setLoading(true);
      setDone(false);
      setError(null);
      if (!question) {
        setEvents([]);
        setCachedResults({});
        setSessionId(null);
      }

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch("/api/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            results,
            params,
            question: question || undefined,
            session_id: question ? sessionId : null,
          }),
          signal: controller.signal,
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6);
            if (data === "[DONE]") {
              setDone(true);
              continue;
            }
            try {
              const event = JSON.parse(data);
              // 捕获首次返回的 session_id
              if (event.type === "meta" && event.session_id) {
                setSessionId(event.session_id);
              }
              // 为回测结果分配唯一缓存 ID
              if (
                event.type === "tool_result" &&
                event.name === "run_backtest" &&
                event.result &&
                !event.result.error
              ) {
                cacheIdRef.current += 1;
                const cid = String(cacheIdRef.current);
                event._cacheId = cid;
                setCachedResults((c) => ({
                  ...c,
                  [cid]: { tool: event.name, ...event.result },
                }));
              }
              setEvents((prev) => [...prev, event]);
            } catch {
              /* skip */
            }
          }
        }
      } catch (e) {
        if (e.name !== "AbortError") {
          setError(e.message);
        }
      } finally {
        setLoading(false);
        abortRef.current = null;
      }
    },
    [action, results, params],
  );

  useEffect(() => {
    startSession("");
    return () => {
      abortRef.current?.abort();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFollowUp = () => {
    if (!followUp.trim() || loading) return;
    startSession(followUp.trim());
    setFollowUp("");
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setLoading(false);
    setDone(true);
  };

  const handleViewChart = async (cacheKey) => {
    const cached = cachedResults[cacheKey];
    if (!cached || !onViewResults) return;

    // 优先用缓存里的股票和日期，没有则从父组件 params 取
    const vtSymbols = cached.vt_symbols || params?.vt_symbols || [];
    const start = cached.start || params?.start || "2024-01-01";
    const end = cached.end || params?.end || "2024-12-31";
    const capital = params?.capital || 1_000_000;
    const strategy = cached.strategy || cached.tool;
    const stratParams = cached.params || {};

    if (!strategy || vtSymbols.length === 0) {
      return;
    }

    // 调后端跑完整回测拿全量 daily + trades
    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vt_symbols: vtSymbols,
          start,
          end,
          capital,
          strategies: [strategy],
          strategy_params: { [strategy]: stratParams },
        }),
      });
      const data = await res.json();
      if (data.results) {
        onViewResults({ task_id: cacheKey, results: data.results });
      }
    } catch {
      // 失败静默忽略
    }
  };

  /* ---- 事件渲染 ---- */

  const renderEvent = (event, idx) => {
    switch (event.type) {
      case "thinking":
        return (
          <div key={idx} className="agent-event thinking">
            <span className="agent-event-text">{event.content}</span>
          </div>
        );

      case "tool_call":
        return (
          <div key={idx} className="agent-event tool-call">
            <span className="agent-event-marker" />
            <span className="agent-event-text">
              调用 <code>{event.name}</code>
              {event.arguments && (
                <span className="agent-tool-args">
                  {" "}
                  {JSON.stringify(event.arguments)}
                </span>
              )}
            </span>
          </div>
        );

      case "tool_result": {
        const cacheId = event._cacheId;
        const isBacktest = !!cacheId;

        return (
          <div key={idx} className="agent-event tool-result">
            <span className="agent-event-marker" />
            <span className="agent-event-text">
              <code>{event.name}</code> 完成
              {event.elapsed_ms != null && (
                <span className="agent-elapsed"> ({event.elapsed_ms}ms)</span>
              )}
              {isBacktest && (
                <button
                  className="agent-view-chart-btn"
                  onClick={() => handleViewChart(cacheId)}
                >
                  查看图表
                </button>
              )}
            </span>
          </div>
        );
      }

      case "done":
        return (
          <div key={idx} className="agent-event answer">
            <div className="agent-answer-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {event.content}
              </ReactMarkdown>
            </div>
          </div>
        );

      case "error":
        return (
          <div key={idx} className="agent-event error">
            <span className="agent-event-text">{event.content}</span>
          </div>
        );

      default:
        return null;
    }
  };

  /* ---- 最小化态 ---- */

  if (minimized) {
    return (
      <div className="agent-panel minimized">
        <button
          className="agent-minimized-tab"
          onClick={() => setMinimized(false)}
          title="展开 Agent"
        >
          Agent
          {loading && <span className="agent-dots-inline">...</span>}
        </button>
      </div>
    );
  }

  return (
    <div className={`agent-panel ${maximized ? "maximized" : ""}`}>
      {/* 头部 */}
      <div className="agent-panel-header">
        <h2>Agent · {label}</h2>
        <div className="agent-panel-actions">
          {loading && (
            <button className="agent-stop-btn" onClick={handleStop}>
              停止
            </button>
          )}
          <button
            className="agent-minimize-btn"
            onClick={() => setMinimized(true)}
            title="最小化"
          >
            —
          </button>
          <button
            className="agent-maximize-btn"
            onClick={() => setMaximized(!maximized)}
            title={maximized ? "还原" : "最大化"}
          >
            {maximized ? <IconRestore size={15} /> : <IconMaximize size={15} />}
          </button>
          <button className="agent-close-btn" onClick={onClose}>
            ✕
          </button>
        </div>
      </div>

      {/* 内容区 */}
      <div className="agent-panel-body">
        {error && (
          <div className="agent-event error">
            <span className="agent-event-text">{error}</span>
          </div>
        )}

        {events.map((event, idx) => renderEvent(event, idx))}

        {loading && !done && (
          <div className="agent-event thinking">
            <span className="agent-event-text agent-loading">
              正在思考
              <span className="agent-dots">
                <span>.</span>
                <span>.</span>
                <span>.</span>
              </span>
            </span>
          </div>
        )}

        {done && !loading && (
          <div className="agent-event thinking done-hint">
            <span className="agent-event-text">
              分析完成，你可以在下方输入框追问。
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 追问输入框 */}
      {done && !loading && (
        <div className="agent-panel-footer">
          <input
            type="text"
            className="agent-followup-input"
            placeholder="追问更多细节..."
            value={followUp}
            onChange={(e) => setFollowUp(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFollowUp()}
          />
          <button
            className="agent-followup-btn"
            onClick={handleFollowUp}
            disabled={!followUp.trim()}
          >
            发送
          </button>
        </div>
      )}
    </div>
  );
}
