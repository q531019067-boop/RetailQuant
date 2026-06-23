"""
rquant — A 股个人量化看板
- business/    业务层（持仓/资金/板块/自选股/标的池）
- data_source/ 数据层（多源路由/本地缓存/消息队列）
- strategy/    策略层（12 个策略 + 注册中心）
- research/    研究层（选池/评分/模拟编排）
- backtest/    回测层（通用回测引擎）
- web/         Web 层（Flask 入口与路由）
- log/         日志层（loguru 封装）
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
