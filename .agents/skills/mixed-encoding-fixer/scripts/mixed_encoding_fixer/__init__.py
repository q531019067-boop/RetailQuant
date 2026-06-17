# -*- coding: utf-8 -*-
"""GBK / UTF-8 混合编码分析与修复 — 内部实现包。

对外 CLI 请使用同目录上一级中的：

- ``fix_encoding.py``：行级分析、probe、auto、recover、local-repair 等；
- ``detect_encoding.py``：整文件编码标签；
- ``mixed_encoding_tool.py``：从任意工作目录统一启动上述工具。

本包无稳定公共 API，子模块供上述脚本引用，勿当作独立入口执行。
"""

__all__: list[str] = []
