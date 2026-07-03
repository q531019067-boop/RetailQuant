/**
 * 前端组件测试
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AgentButton from "./components/AgentButton";
import CompareTable from "./components/CompareTable";
import TradeTable from "./components/TradeTable";

// ═══════════════════════════════════════════════════════════════
// AgentButton
// ═══════════════════════════════════════════════════════════════

/** 模拟点击：mousedown + mouseup（匹配组件的 document 级监听） */
function clickBtn(el) {
  fireEvent.mouseDown(el, { button: 0 });
  fireEvent.mouseUp(el, { button: 0 });
}

describe("AgentButton", () => {
  it("renders the button", () => {
    render(
      <AgentButton onSelect={vi.fn()} hasResults={false} disabled={false} />,
    );
    expect(screen.getByLabelText("AI 助手")).toBeInTheDocument();
  });

  it("opens menu on click", async () => {
    render(
      <AgentButton onSelect={vi.fn()} hasResults={true} disabled={false} />,
    );
    clickBtn(screen.getByLabelText("AI 助手"));
    await waitFor(() =>
      expect(screen.getByText("分析回测")).toBeInTheDocument(),
    );
    expect(screen.getByText("优化参数")).toBeInTheDocument();
  });

  it("blocks result-dependent items when no results", async () => {
    render(
      <AgentButton onSelect={vi.fn()} hasResults={false} disabled={false} />,
    );
    clickBtn(screen.getByLabelText("AI 助手"));
    await waitFor(() => expect(screen.getAllByText("需回测").length).toBe(2));
  });

  it("allows all items when has results", async () => {
    render(
      <AgentButton onSelect={vi.fn()} hasResults={true} disabled={false} />,
    );
    clickBtn(screen.getByLabelText("AI 助手"));
    await waitFor(() =>
      expect(screen.queryByText("需回测")).not.toBeInTheDocument(),
    );
  });

  it("calls onSelect with correct action key", async () => {
    const fn = vi.fn();
    render(<AgentButton onSelect={fn} hasResults={true} disabled={false} />);
    clickBtn(screen.getByLabelText("AI 助手"));
    await waitFor(() => fireEvent.click(screen.getByText("优化参数")));
    expect(fn).toHaveBeenCalledWith("optimize");
  });

  it("does not call onSelect when blocked", async () => {
    const fn = vi.fn();
    render(<AgentButton onSelect={fn} hasResults={false} disabled={false} />);
    clickBtn(screen.getByLabelText("AI 助手"));
    await waitFor(() => fireEvent.click(screen.getByText("分析回测")));
    expect(fn).not.toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════════════════════
// CompareTable
// ═══════════════════════════════════════════════════════════════

const metricRows = [
  {
    key: "sharpe_ratio",
    label: "Sharpe",
    fmt: (v) => v.toFixed(2),
    better: "higher",
  },
  {
    key: "max_ddpercent",
    label: "回撤",
    fmt: (v) => `${v.toFixed(1)}%`,
    better: "lower",
  },
];

describe("CompareTable", () => {
  it("renders strategy names and metrics", () => {
    render(
      <CompareTable
        stratNames={["equal_weight", "vp_breakout"]}
        stratMeta={{
          equal_weight: { label: "动量轮动" },
          vp_breakout: { label: "量价突破" },
        }}
        results={{
          equal_weight: {
            statistics: { sharpe_ratio: 1.2, max_ddpercent: -15 },
          },
          vp_breakout: {
            statistics: { sharpe_ratio: 1.5, max_ddpercent: -10 },
          },
        }}
        metricRows={metricRows}
        show={true}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("动量轮动")).toBeInTheDocument();
    expect(screen.getByText("Sharpe")).toBeInTheDocument();
  });

  it("highlights best value", () => {
    render(
      <CompareTable
        stratNames={["a", "b"]}
        stratMeta={{ a: { label: "A" }, b: { label: "B" } }}
        results={{
          a: { statistics: { sharpe_ratio: 1.0 } },
          b: { statistics: { sharpe_ratio: 2.0 } },
        }}
        metricRows={metricRows}
        show={true}
        onToggle={vi.fn()}
      />,
    );
    expect(document.querySelectorAll(".best").length).toBeGreaterThan(0);
  });

  it("hides table when show is false", () => {
    render(
      <CompareTable
        stratNames={["a"]}
        stratMeta={{ a: { label: "A" } }}
        results={{ a: { statistics: { sharpe_ratio: 1.0 } } }}
        metricRows={metricRows}
        show={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.queryByText("Sharpe")).not.toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════
// TradeTable
// ═══════════════════════════════════════════════════════════════

const sampleTrades = [
  {
    date: "2024-01-05",
    symbol: "600519.SSE",
    side: "买入开仓",
    price: 1800,
    shares: 100,
    entry_price: null,
    pnl: null,
    pnl_pct: null,
  },
  {
    date: "2024-02-10",
    symbol: "600519.SSE",
    side: "卖出平仓",
    price: 1900,
    shares: 100,
    entry_price: 1800,
    pnl: 10000,
    pnl_pct: 5.5,
  },
];

describe("TradeTable", () => {
  it("renders trade rows", () => {
    render(
      <TradeTable
        trades={sampleTrades}
        stockNames={{}}
        label="动量轮动"
        show={true}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText((c) => c.includes("动量轮动"))).toBeInTheDocument();
    expect(screen.getByText("买入开仓")).toBeInTheDocument();
  });

  it("returns null when no trades", () => {
    const { container } = render(
      <TradeTable
        trades={[]}
        stockNames={{}}
        label="X"
        show={true}
        onToggle={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("shows stock name from mapping", () => {
    render(
      <TradeTable
        trades={sampleTrades}
        stockNames={{ "600519.SSE": "贵州茅台" }}
        label="动量轮动"
        show={true}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getAllByText("贵州茅台").length).toBe(2);
  });
});
