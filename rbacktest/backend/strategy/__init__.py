"""
策略包 —— 导入子模块即触发 BaseStrategy.__init_subclass__ 自动注册。

加新策略只需：
    1. 新建 strategy/xxx.py，继承 BaseStrategy
    2. 在这里加一行 import

无需修改 registry、engine、app.py 中的任何映射表。
"""

from .base import BaseStrategy
from .registry import all_strategies, get_strategy, list_strategies_metadata

# 导入各策略模块 → 触发 __init_subclass__ → 自动注册
from . import equal_weight  # noqa: F401
from . import grid_martingale  # noqa: F401
from . import vp_breakout  # noqa: F401

__all__ = [
    "BaseStrategy",
    "all_strategies",
    "get_strategy",
    "list_strategies_metadata",
]
