# -*- coding: utf-8 -*-
import json
import sys
from typing import List, Optional


def emit_error(
    code: str,
    message: str,
    suggestions: Optional[List[str]] = None,
    stream=None,
) -> None:
    stream = stream or sys.stderr
    obj = {
        "status": "error",
        "error_code": code,
        "message": message,
        "suggestions": suggestions or [],
    }
    stream.write(json.dumps(obj, ensure_ascii=False) + "\n")


def emit_verbose(msg: str, verbose: bool) -> None:
    if verbose:
        print(msg, file=sys.stderr)
