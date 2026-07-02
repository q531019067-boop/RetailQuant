const API_BASE = "";

/**
 * Fetch all available stock symbols from the backend.
 * @returns {Promise<string[]>}
 */
export async function fetchStocks() {
  const res = await fetch(`${API_BASE}/api/stocks`);
  const data = await res.json();
  return data.stocks;
}

/**
 * Fetch strategy metadata (name, label, params schema).
 * @returns {Promise<Array<{name: string, label: string, params: Object}>>}
 */
export async function fetchStrategies() {
  const res = await fetch(`${API_BASE}/api/strategies`);
  const data = await res.json();
  return data.strategies;
}

/**
 * Submit backtest parameters and return results.
 * @param {Object} params - vt_symbols, start, end, capital, strategies, ...
 * @returns {Promise<{task_id: string, results: Object}>}
 */
export async function runBacktest(params) {
  const res = await fetch(`${API_BASE}/api/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Backtest failed");
  }
  return res.json();
}

/**
 * Fetch stock name mapping.
 * @param {string[]} codes - optional list of codes to filter
 * @returns {Promise<{names: Object, count: number}>}
 */
export async function fetchStockNames(codes) {
  const params = codes && codes.length ? `?codes=${codes.join(",")}` : "";
  const res = await fetch(`${API_BASE}/api/stock-names${params}`);
  return res.json();
}

/**
 * Fetch benchmark (e.g., CSI 300) daily NAV.
 * @param {string} code - benchmark code, default "000300.SSE"
 * @param {string} start - start date "YYYY-MM-DD"
 * @param {string} end - end date "YYYY-MM-DD"
 * @returns {Promise<{code: string, dates: string[], nav: number[]}>}
 */
export async function fetchBenchmark(code, start, end) {
  const params = new URLSearchParams({ code, start, end });
  const res = await fetch(`${API_BASE}/api/benchmark?${params}`);
  if (!res.ok) return null;
  return res.json();
}

/* ------------------------------------------------------------------ */
/*  localStorage 持久化                                                */
/* ------------------------------------------------------------------ */

const HISTORY_KEY = "rbacktest_history";
const MAX_HISTORY = 20;

/**
 * Save a backtest result to localStorage.
 * @param {Object} entry - { task_id, params, results, saved_at }
 */
export function saveToHistory(entry) {
  try {
    const history = loadHistory();
    history.unshift(entry);
    if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    /* quota exceeded or disabled — silently skip */
  }
}

/**
 * Load all saved backtest entries.
 * @returns {Array<{task_id: string, params: Object, results: Object, saved_at: string}>}
 */
export function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

/**
 * Delete a single history entry by task_id.
 */
export function deleteFromHistory(taskId) {
  const history = loadHistory().filter((e) => e.task_id !== taskId);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

/**
 * Clear all history.
 */
export function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
}
