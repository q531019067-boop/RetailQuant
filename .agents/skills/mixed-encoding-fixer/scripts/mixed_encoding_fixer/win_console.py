# -*- coding: utf-8 -*-
"""Windows 下尽量将标准流设为 UTF-8，减轻中文路径与标签在控制台的乱码。"""
from __future__ import annotations

import sys


def try_reconfigure_stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if not callable(reconf):
            continue
        try:
            reconf(encoding="utf-8")
        except (OSError, ValueError, TypeError, AttributeError):
            pass
