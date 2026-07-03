"""
项目日志模块 —— 同时输出到控制台和文件。

用法:
    from backend.log import logger
    logger.info("something")
    logger.error("something", exc_info=True)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "agent.log"


def _setup_logger() -> logging.Logger:
    """配置 logger，同时输出到控制台和 daily rotating file。"""
    logger = logging.getLogger("rbacktest")
    logger.setLevel(logging.DEBUG)

    # 避免重复 handler
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%m-%d %H:%M:%S",
    )

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件（自动创建目录）
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = _setup_logger()
