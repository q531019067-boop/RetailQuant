"""
策略注册中心 —— 任何继承 BaseStrategy 的类自动注册，无需手动维护映射表。

用法：
    from .base import BaseStrategy

    class MyStrategy(BaseStrategy):
        name = "my_strategy"
        label = "我的策略"
        ...
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseStrategy

_registry: dict[str, type["BaseStrategy"]] = {}


def _register(cls: type["BaseStrategy"]) -> type["BaseStrategy"]:
    """内部注册函数 —— 由 BaseStrategy.__init_subclass__ 自动调用。"""
    name = getattr(cls, "name", "")
    if not name:
        raise TypeError(f"策略类 {cls.__name__} 必须定义 `name` 属性")
    if name in _registry:
        raise ValueError(f"策略名重复: {name!r}（{cls.__name__} 与 {_registry[name].__name__}）")
    _registry[name] = cls
    return cls


def all_strategies() -> list[type["BaseStrategy"]]:
    """返回所有已注册的策略类。"""
    return list(_registry.values())


def get_strategy(name: str) -> type["BaseStrategy"] | None:
    """按名称获取策略类。"""
    return _registry.get(name)


def list_strategies_metadata() -> list[dict]:
    """生成前端策略列表 API 响应 —— 单一数据源，无需手写 JSON。

    自动从策略类的 name / label / description / param_schema() 生成。
    """
    result: list[dict] = []
    for cls in _registry.values():
        result.append(
            {
                "name": cls.name,
                "label": cls.label,
                "description": cls.description,
                "color": cls.color,
                "params": cls.param_schema(),
            }
        )
    return result
