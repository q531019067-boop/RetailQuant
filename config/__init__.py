"""config — 全局配置

用法：
    from config import config
    print(config.server.port)
"""

from .config import config  # noqa: F401

__all__ = ["config"]
