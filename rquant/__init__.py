"""
rquant — A 股个人量化看板
- business/    业务层（数据/板块/持仓/大盘）
- data_source/ 数据层（Sina + 数据池）
- strategy/    策略层（10 个策略 + 路由器）
- web/         Web 层（Flask）
"""

from . import business, data_source, strategy, web

__version__ = "0.2.0"

__all__ = [
    "business",
    "data_source",
    "strategy",
    "web",
    "__version__",
]
