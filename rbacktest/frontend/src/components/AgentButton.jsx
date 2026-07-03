/**
 * 浮动 Agent 按钮 —— 可拖动圆形按钮 + 弹出菜单。
 *
 * 拖动方案：mousedown 记录起点 → document mousemove 更新位置 → mouseup 判断拖拽/点击。
 */

import { useState, useRef, useCallback, useEffect } from "react";

/* ------------------------------------------------------------------ */
/*  SVG 图标                                                          */
/* ------------------------------------------------------------------ */

function IconSparkle({ size = 24 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z" />
      <path d="M4 4l.5 1.5L6 6l-1.5.5L4 8l-.5-1.5L2 6l1.5-.5z" opacity="0.5" />
      <path d="M19 17l.3.7.7.3-.7.3-.3.7-.3-.7-.7.3.7-.3z" opacity="0.5" />
    </svg>
  );
}

function IconChart({ size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="3 20 9 12 14 15 21 7" />
      <polyline points="21 7 15 7 15 13" />
    </svg>
  );
}

function IconSettings({ size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function IconAlert({ size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2L2 22h20L12 2z" />
      <line x1="12" y1="10" x2="12" y2="15" />
      <circle cx="12" cy="18.5" r="0.8" fill="currentColor" stroke="none" />
    </svg>
  );
}

function IconGrid({ size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="3" width="7" height="7" rx="1.2" />
      <rect x="14" y="3" width="7" height="7" rx="1.2" />
      <rect x="3" y="14" width="7" height="7" rx="1.2" />
      <rect x="14" y="14" width="7" height="7" rx="1.2" />
    </svg>
  );
}

function IconClose({ size = 22 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <line x1="7" y1="7" x2="17" y2="17" />
      <line x1="17" y1="7" x2="7" y2="17" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* 菜单项                                                              */
/* ------------------------------------------------------------------ */

const MENU_ITEMS = [
  { key: "analyze", label: "分析回测", Icon: IconChart, needsResults: true },
  {
    key: "optimize",
    label: "优化参数",
    Icon: IconSettings,
    needsResults: false,
  },
  { key: "risk", label: "风险诊断", Icon: IconAlert, needsResults: true },
  { key: "explore", label: "批量探索", Icon: IconGrid, needsResults: false },
];

/* ------------------------------------------------------------------ */

const THRESHOLD = 4; // px，超过此距离算拖拽

export default function AgentButton({ onSelect, hasResults, disabled }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ x: 28, y: 28 });
  const rootRef = useRef(null);
  const dragging = useRef({
    active: false,
    sx: 0,
    sy: 0,
    ox: 0,
    oy: 0,
    moved: false,
    frame: 0,
  });

  /* ---- 拖拽逻辑（document 级监听，通用方案） ---- */

  const onMouseDown = useCallback(
    (e) => {
      // 只响应左键；忽略菜单内的点击
      if (e.button !== 0) return;
      const d = dragging.current;
      d.active = true;
      d.sx = e.clientX;
      d.sy = e.clientY;
      d.ox = pos.x;
      d.oy = pos.y;
      d.moved = false;
      e.preventDefault();
    },
    [pos],
  );

  useEffect(() => {
    const onMove = (e) => {
      const d = dragging.current;
      if (!d.active) return;
      const dx = e.clientX - d.sx;
      const dy = e.clientY - d.sy;
      if (Math.abs(dx) > THRESHOLD || Math.abs(dy) > THRESHOLD) d.moved = true;
      if (!d.moved) return;
      // requestAnimationFrame 节流
      if (d.frame) return;
      d.frame = requestAnimationFrame(() => {
        d.frame = 0;
        setPos({
          x: Math.max(8, Math.min(window.innerWidth - 64, d.ox + dx)),
          y: Math.max(8, Math.min(window.innerHeight - 64, d.oy + dy)),
        });
      });
    };

    const onUp = () => {
      const d = dragging.current;
      if (!d.active) return;
      d.active = false;
      if (d.frame) cancelAnimationFrame(d.frame);
      d.frame = 0;
      // 没有移动 → 视为点击
      if (!d.moved && !disabled) {
        setOpen((p) => !p);
      }
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [disabled]);

  /* ---- 窗口缩放修正 ---- */

  useEffect(() => {
    const r = () =>
      setPos((p) => ({
        x: Math.min(p.x, window.innerWidth - 64),
        y: Math.min(p.y, window.innerHeight - 64),
      }));
    window.addEventListener("resize", r);
    return () => window.removeEventListener("resize", r);
  }, []);

  return (
    <div
      ref={rootRef}
      className={`agent-fab-root ${disabled ? "is-busy" : ""}`}
      style={{ right: pos.x, bottom: pos.y, left: "auto", top: "auto" }}
    >
      {open && (
        <>
          <div className="agent-fab-backdrop" onClick={() => setOpen(false)} />
          <div className="agent-fab-menu" onClick={(e) => e.stopPropagation()}>
            <div className="agent-fab-menu-title">AI 助手</div>
            {MENU_ITEMS.map(({ key, label, Icon, needsResults }) => {
              const blocked = needsResults && !hasResults;
              return (
                <button
                  key={key}
                  className={`agent-fab-menu-item ${blocked ? "is-blocked" : ""}`}
                  disabled={blocked || disabled}
                  onClick={() => {
                    if (!blocked) {
                      onSelect(key);
                      setOpen(false);
                    }
                  }}
                >
                  <span className="agent-fab-menu-icon">
                    <Icon size={16} />
                  </span>
                  <span className="agent-fab-menu-label">{label}</span>
                  {blocked && (
                    <span className="agent-fab-menu-hint">需回测</span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}

      <button
        className={`agent-fab-btn ${open ? "is-open" : ""}`}
        disabled={disabled}
        aria-label="AI 助手"
        onMouseDown={onMouseDown}
      >
        {open ? <IconClose size={20} /> : <IconSparkle size={22} />}
      </button>
    </div>
  );
}
