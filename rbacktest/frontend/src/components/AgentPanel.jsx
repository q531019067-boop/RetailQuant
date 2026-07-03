/**
 * Agent 对话面板 —— 右侧滑入，不阻塞主界面。
 *
 * - 无遮罩层，主界面始终可操作
 * - 可最小化为侧边标签、最大化
 * - 自由对话：用户输入需求，AI 自主判断该分析还是跑回测
 * - 缓存 tool 返回的回测结果，点击「查看图表」注入主视图
 */

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* ------------------------------------------------------------------ */
/*  SVG 图标                                                          */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  示例问题（轮播显示在输入框 placeholder）                              */
/* ------------------------------------------------------------------ */

const HINTS = [
  "帮我分析这次回测的表现",
  "优化这个策略的参数",
  "对比所有可用策略",
  "这个回测有什么风险点？",
  "帮我解读最大回撤的原因",
];

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

export default function AgentPanel({
  results,
  params,
  sessionData,
  onClose,
  onViewResults,
}) {
  const [events, setEvents] = useState(sessionData?.events || []);
  const [done, setDone] = useState(!!sessionData);
  const [error, setError] = useState(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [cachedResults, setCachedResults] = useState(
    sessionData?.cached_results || {},
  );
  const [sessionId, setSessionId] = useState(sessionData?.id || null);
  const [hintIdx, setHintIdx] = useState(0);
  const [hasSent, setHasSent] = useState(!!sessionData);
  const isReplay = !!sessionData;
  const cacheIdRef = useRef(0);
  const bottomRef = useRef(null);
  const abortRef = useRef(null);
  const initialResultsRef = useRef(results);
  const dataChanged = results !== initialResultsRef.current && results != null;
  const firstQuestionRef = useRef("");

  // session 完成时自动保存到后端文件
  useEffect(() => {
    if (!done || !sessionId) return;
    const save = async () => {
      try {
        // 拉取所有缓存的全量回测结果（含 daily + trades），嵌入文件避免重启丢失
        const cachedWithFull: Record<string, unknown> = {};
        for (const [cid, entry] of Object.entries(cachedResults)) {
          cachedWithFull[cid] = { ...entry };
          const cacheId = (entry as Record<string, unknown>)?._cache_id as string | undefined;
          if (cacheId) {
            try {
              const res = await fetch(`/api/agent/result/${cacheId}`);
              if (res.ok) {
                const full = await res.json();
                cachedWithFull[cid]._full_data = full;
              }
            } catch {
              /* ignore */
            }
          }
        }
        await fetch("/api/agent/sessions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: sessionId,
            first_question: firstQuestionRef.current,
            events: events.filter((e) => e.type !== "heartbeat"),
            cached_results: cachedWithFull,
          }),
        });
      } catch {
        /* ignore */
      }
    };
    save();
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps

  // 轮播 placeholder
  useEffect(() => {
    const timer = setInterval(
      () => setHintIdx((i) => (i + 1) % HINTS.length),
      3000,
    );
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  /* ---- 压缩 results 为摘要 ---- */

  const resultsSummary = useCallback(() => {
    if (!results || !results.results) return null;
    const summary = {};
    for (const [sn, r] of Object.entries(results.results)) {
      summary[sn] = {
        statistics: r.statistics || {},
        daily: (r.daily || []).slice(0, 2),
        trades: (r.trades || []).slice(0, 5),
      };
    }
    return { results: summary };
  }, [results]);

  /* ---- 发送消息 & SSE 流处理 ---- */

  const sendMessage = useCallback(
    async (question) => {
      const q = question.trim();
      if (!q || loading) return;
      setLoading(true);
      setDone(false);
      setError(null);
      setHasSent(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch("/api/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            results: resultsSummary(),
            params,
            question: q,
            session_id: sessionId,
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
              if (event.type === "heartbeat") continue;
              if (event.type === "meta" && event.session_id) {
                setSessionId(event.session_id);
                continue;
              }
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
        if (e.name !== "AbortError") setError(e.message);
      } finally {
        setLoading(false);
        abortRef.current = null;
      }
    },
    [resultsSummary, params, sessionId, loading],
  );

  /* ---- 操作 ---- */

  const handleSend = () => {
    if (!input.trim() || loading) return;
    if (!firstQuestionRef.current) firstQuestionRef.current = input.trim();
    sendMessage(input);
    setInput("");
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setLoading(false);
    setDone(true);
  };

  const handleViewChart = async (cacheKey) => {
    const cached = cachedResults[cacheKey];
    if (!cached || !onViewResults) return;

    // 优先用保存的全量数据（回放模式，无需 API）
    if (cached._full_data?.results) {
      onViewResults({ task_id: cacheKey, results: cached._full_data.results });
      return;
    }

    // 其次查后端内存缓存
    if (cached._cache_id) {
      try {
        const res = await fetch(`/api/agent/result/${cached._cache_id}`);
        if (res.ok) {
          const data = await res.json();
          if (data.results) {
            onViewResults({ task_id: cacheKey, results: data.results });
            return;
          }
        }
      } catch {
        /* fallback */
      }
    }

    const vtSymbols = cached.vt_symbols || params?.vt_symbols || [];
    const start = cached.start || params?.start || "2024-01-01";
    const end = cached.end || params?.end || "2024-12-31";
    const capital = cached.capital || params?.capital || 1_000_000;
    // 兼容单策略旧格式（cached.strategy）和多策略新格式（cached.strategies）
    const strats =
      cached.strategies || [cached.strategy || cached.tool].filter(Boolean);
    const stratParams = cached.strategy_params || cached.params || {};
    if (strats.length === 0 || vtSymbols.length === 0) return;

    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vt_symbols: vtSymbols,
          start,
          end,
          capital,
          strategies: strats,
          strategy_params: stratParams,
        }),
      });
      const data = await res.json();
      if (data.results)
        onViewResults({ task_id: cacheKey, results: data.results });
    } catch {
      /* ignore */
    }
  };

  /* ---- 事件渲染 ---- */

  const renderEvent = (event, idx) => {
    const k = idx;
    switch (event.type) {
      case "thinking":
        return (
          <div key={k} className="agent-event thinking">
            <span className="agent-event-text">{event.content}</span>
          </div>
        );
      case "tool_call":
        return (
          <div key={k} className="agent-event tool-call">
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
        const cid = event._cacheId;
        return (
          <div key={k} className="agent-event tool-result">
            <span className="agent-event-marker" />
            <span className="agent-event-text">
              <code>{event.name}</code> 完成
              {event.elapsed_ms != null && (
                <span className="agent-elapsed"> ({event.elapsed_ms}ms)</span>
              )}
              {!!cid && (
                <button
                  className="agent-view-chart-btn"
                  onClick={() => handleViewChart(cid)}
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
          <div key={k} className="agent-event answer">
            <div className="agent-answer-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {event.content}
              </ReactMarkdown>
            </div>
          </div>
        );
      case "error":
        return (
          <div key={k} className="agent-event error">
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
          Agent {loading && <span className="agent-dots-inline">...</span>}
        </button>
      </div>
    );
  }

  return (
    <div className={`agent-panel ${maximized ? "maximized" : ""}`}>
      {/* 头部 */}
      <div className="agent-panel-header">
        <h2>AI 助手{isReplay ? " · 历史回放" : ""}</h2>
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
        {dataChanged && (
          <div
            style={{
              color: "#fa8c16",
              padding: "8px",
              background: "#fffbe6",
              borderRadius: "6px",
              marginBottom: "8px",
              fontSize: "0.82rem",
            }}
          >
            ⚠ 回测数据已更新。当前分析基于旧数据，建议关闭面板后重新打开。
          </div>
        )}

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

        <div ref={bottomRef} />
      </div>

      {/* 输入框 —— 回放模式隐藏 */}
      {!isReplay && (
        <div className="agent-panel-footer">
          <input
            type="text"
            className="agent-followup-input"
            placeholder={HINTS[hintIdx]}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
          />
          <button
            className="agent-followup-btn"
            onClick={handleSend}
            disabled={!input.trim() || loading}
          >
            发送
          </button>
        </div>
      )}
    </div>
  );
}
