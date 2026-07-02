"""
策略基类 —— 所有策略继承此类即可获得自动注册 + 参数 schema 生成。

设计：
    - 继承 vnpy.alpha.AlphaStrategy，保证与 VNPY 回测引擎完全兼容
    - __init_subclass__ 自动触发注册，无需装饰器
    - _param_meta 字典一次性定义参数的前端元数据（类型/范围/标签）
    - param_schema() 自动合并 class annotations + _param_meta 生成 API schema

子类最小示例：

    class MyStrategy(BaseStrategy):
        name = "my_strat"
        label = "我的策略"
        description = "策略说明"
        color = "#eb2f96"

        # VNPY 参数 —— 类型注解 + 默认值
        lookback: int = 20
        top_k: int = 5

        # 前端参数 schema —— 与上面一一对应
        _param_meta = {
            "lookback": {"type": "int", "min": 5, "max": 120, "label": "回顾天数"},
            "top_k":    {"type": "int", "min": 1, "max": 30, "label": "持仓数量"},
        }

        def on_init(self): ...
        def on_bars(self, bars): ...
        def on_trade(self, trade): ...
"""

from __future__ import annotations

from vnpy.alpha import AlphaStrategy


class BaseStrategy(AlphaStrategy):
    """公共策略基类。

    类属性：
        name: str         唯一 ID（如 "equal_weight"）
        label: str        中文标签，前端展示用
        description: str  一句话说明
        color: str        前端折线图颜色（hex，如 "#cf1322"）
        _param_meta: dict 参数元数据，key=参数名，value={type, min, max, step, label}
    """

    name: str = ""
    label: str = ""
    description: str = ""
    color: str = "#333333"

    # 注意：不在基类设 _param_meta = {}，避免子类间意外共享可变默认值。
    # param_schema() 内部用 getattr(cls, '_param_meta', {}) 安全读取。

    # ---- 子类可覆盖的缓存配置 ----
    bar_history: dict[str, list]  # 由 _maintain_bars 自动管理
    max_cache: int = 120  # 默认保留 120 根 K 线，子类在 on_init 中按需覆盖

    def _maintain_bars(self, bars: dict) -> None:
        """维护滑动窗口 bar 缓存。所有子类在 on_bars 开头调用此方法即可。"""
        if not hasattr(self, "bar_history"):
            self.bar_history = {}
        for sym, bar in bars.items():
            if sym not in self.bar_history:
                self.bar_history[sym] = []
            self.bar_history[sym].append(bar)
            if len(self.bar_history[sym]) > self.max_cache:
                self.bar_history[sym] = self.bar_history[sym][-self.max_cache :]

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # 检查子类自己的 __dict__（非继承），确保显式定义了 name
        if "name" not in cls.__dict__:
            raise TypeError(f'策略类 {cls.__name__} 必须定义 `name` 类属性，如 name = "my_strategy"')
        from .registry import _register

        _register(cls)

    # ---- 参数 schema -------------------------------------------------

    @classmethod
    def param_schema(cls) -> dict[str, dict]:
        """生成前端参数面板的 schema。

        合并来源：
            1. __annotations__  → 获取参数名和 Python 类型
            2. _param_meta      → 获取 min/max/step/label 等 UI 元数据
            3. 类属性默认值      → 作为 default

        Returns:
            {param_name: {type, default, min, max, step, label}}
        """
        schema: dict[str, dict] = {}
        annotations = cls.__annotations__ if hasattr(cls, "__annotations__") else {}

        for attr_name, py_type in annotations.items():
            if attr_name.startswith("_"):
                continue  # 跳过私有属性

            meta = getattr(cls, "_param_meta", {}).get(attr_name, {})
            default = getattr(cls, attr_name, None)

            entry: dict = {
                "type": meta.get("type", _python_type_to_json_type(py_type)),
                "default": default,
                "label": meta.get("label", attr_name),
            }

            if "min" in meta:
                entry["min"] = meta["min"]
            if "max" in meta:
                entry["max"] = meta["max"]
            if "step" in meta:
                entry["step"] = meta["step"]

            schema[attr_name] = entry

        return schema


def _python_type_to_json_type(py_type: type) -> str:
    """映射 Python 类型 → 前端 JSON schema 类型。"""
    origin = getattr(py_type, "__origin__", None) or py_type
    if origin is int:
        return "int"
    if origin is float:
        return "float"
    if origin is bool:
        return "bool"
    return "string"


def calc_shares(target_value: float, price: float, cash_available: float | None = None) -> float:
    """根据目标金额计算可买股数。

    VNPY 内部自行处理手数取整，本函数只做资金约束的下限截断。
    策略通用工具：所有子类在 on_bars 中建仓时调用此函数。
    """
    if price <= 0:
        return 0.0
    shares: float = float(int(target_value / price))
    if cash_available is not None:
        shares = min(shares, float(int(cash_available / price)))
    return max(shares, 0.0)


# ---------------------------------------------------------------------------
# 共享技术指标 —— 所有策略子类可直接引用，避免跨文件重复定义
# ---------------------------------------------------------------------------


def _ma_from_bars(hist: list, n: int) -> float:
    """N 日收盘均价，基于 BarData 列表。"""
    if len(hist) < n:
        return float(hist[-1].close_price)
    return float(sum(b.close_price for b in hist[-n:]) / n)


def _calc_rsi(hist: list, n: int = 14) -> float:
    """标准 Wilder RSI(N)。"""
    if len(hist) < n + 1:
        return 50.0
    closes = [b.close_price for b in hist[-(n + 1) :]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0.0)
        losses.append(-diff if diff < 0 else 0.0)
    avg_gain = sum(gains) / len(gains)
    avg_loss = sum(losses) / len(losses)
    if avg_loss == 0:
        return 100.0
    return float(100 - 100 / (1 + avg_gain / avg_loss))


def _calc_atr(hist: list, n: int) -> float:
    """ATR(N) —— Average True Range。"""
    if len(hist) < n + 1:
        return 0.0
    tr_values: list[float] = []
    recent = hist[-n:]
    prev_close = hist[-(n + 1)].close_price
    for b in recent:
        tr = max(
            b.high_price - b.low_price,
            abs(b.high_price - prev_close),
            abs(b.low_price - prev_close),
        )
        tr_values.append(tr)
        prev_close = b.close_price
    return float(sum(tr_values) / len(tr_values)) if tr_values else 0.0
