"""
rQuant 启动入口（向后兼容）
- 老用户用 `python3 app.py` 仍能启动
- 内部转发到 rquant.web.app_factory.run()
"""

import sys
from pathlib import Path

# 让 rquant 包可 import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rquant.web.app_factory import run  # noqa: E402

if __name__ == "__main__":
    run()
