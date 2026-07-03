/**
 * 浮动 Agent 按钮 —— 可拖动圆形按钮，点击直接打开对话面板。
 */

import { useState, useRef, useCallback, useEffect } from "react";

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

const THRESHOLD = 4;

export default function AgentButton({ onToggle }) {
  const [pos, setPos] = useState({ x: 28, y: 80 });
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

  const onMouseDown = useCallback(
    (e) => {
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
      if (
        Math.abs(e.clientX - d.sx) > THRESHOLD ||
        Math.abs(e.clientY - d.sy) > THRESHOLD
      )
        d.moved = true;
      if (!d.moved) return;
      if (d.frame) return;
      d.frame = requestAnimationFrame(() => {
        d.frame = 0;
        setPos({
          x: Math.max(
            8,
            Math.min(window.innerWidth - 64, d.ox + e.clientX - d.sx),
          ),
          y: Math.max(
            60,
            Math.min(window.innerHeight - 64, d.oy + e.clientY - d.sy),
          ),
        });
      });
    };
    const onUp = () => {
      const d = dragging.current;
      if (!d.active) return;
      d.active = false;
      if (d.frame) cancelAnimationFrame(d.frame);
      d.frame = 0;
      if (!d.moved) onToggle();
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [onToggle]);

  useEffect(() => {
    const r = () =>
      setPos((p) => ({
        x: Math.min(p.x, window.innerWidth - 64),
        y: Math.min(Math.max(p.y, 60), window.innerHeight - 64),
      }));
    window.addEventListener("resize", r);
    return () => window.removeEventListener("resize", r);
  }, []);

  return (
    <div
      ref={rootRef}
      className="agent-fab-root"
      style={{ right: pos.x, bottom: pos.y, left: "auto", top: "auto" }}
    >
      <button
        className="agent-fab-btn"
        aria-label="AI 助手"
        onMouseDown={onMouseDown}
      >
        <IconSparkle size={22} />
      </button>
    </div>
  );
}
