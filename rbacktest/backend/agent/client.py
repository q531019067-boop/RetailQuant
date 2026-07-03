"""
LLM 客户端 —— 封装 OpenAI 兼容 API 调用。

设计：
    - 只关心 messages + tools → response，不泄漏底层 provider 细节
    - 通过配置文件切换 DeepSeek / OpenAI / 本地模型
    - 加载时校验配置文件，异常值给出明确警告
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from openai import OpenAI

_log = logging.getLogger("rbacktest")

# ---------------------------------------------------------------------------
# 配置校验
# ---------------------------------------------------------------------------

# 每个 [agent] 字段的约束：{key: (类型, 是否必填, 最小值, 最大值, 描述)}
_AGENT_CONFIG_SCHEMA: dict[str, tuple[type, bool, object, object, str]] = {
    "model": (str, True, None, None, "模型名称"),
    "base_url": (str, True, None, None, "API 地址（需以 http 开头）"),
    "api_key_env": (str, True, None, None, "API key 环境变量名"),
    "max_iterations": (int, True, 1, 200, "最大循环轮数"),
    "temperature": (float, False, 0.0, 2.0, "温度"),
    "max_tokens": (int, False, 100, 128000, "最大 token 数"),
    "timeout_per_step": (float, False, 1, 300, "单步超时秒数"),
}


def _validate_agent_config(cfg: dict) -> list[str]:
    """校验 [agent] 配置节，返回警告列表（空 = 全部合法）。"""
    warnings: list[str] = []
    for key, (typ, required, vmin, vmax, desc) in _AGENT_CONFIG_SCHEMA.items():
        if key not in cfg or cfg[key] is None:
            if required:
                warnings.append(f"[agent] 缺少必填字段 {key}（{desc}），将使用默认值")
            continue
        val = cfg[key]
        if not isinstance(val, typ):
            try:
                val = typ(val)
                cfg[key] = val
            except (ValueError, TypeError):
                warnings.append(f"[agent] {key} 类型错误：期望 {typ.__name__}，实际 {type(val).__name__}，将使用默认值")
                del cfg[key]
                continue
        if vmin is not None and val < vmin:
            warnings.append(f"[agent] {key}={val} 低于最小值 {vmin}（{desc}），已修正为 {vmin}")
            cfg[key] = vmin
        if vmax is not None and val > vmax:
            warnings.append(f"[agent] {key}={val} 超过最大值 {vmax}（{desc}），已修正为 {vmax}")
            cfg[key] = vmax
    # base_url 特殊校验
    if cfg.get("base_url") and not str(cfg["base_url"]).startswith(("http://", "https://")):
        warnings.append(f"[agent] base_url={cfg['base_url']} 不是有效 URL，需以 http:// 或 https:// 开头")
    return warnings


def _load_agent_config() -> dict:
    """从 rbacktest.toml 加载 [agent] 配置节，校验并修正异常值。"""
    config_path = Path(__file__).resolve().parent.parent.parent / "rbacktest.toml"
    cfg: dict = {}
    try:
        if config_path.exists():
            import tomllib

            raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
            cfg = raw.get("agent", {})
    except Exception as e:
        _log.warning(f"读取 rbacktest.toml 失败: {e}，使用默认配置")
        return cfg

    # 校验并输出警告
    warnings = _validate_agent_config(cfg)
    for w in warnings:
        _log.warning(w)
    return cfg


# 公开别名：其他模块可通过 client.load_agent_config() 读取配置
load_agent_config = _load_agent_config


class LLMClient:
    """OpenAI 兼容的 LLM 客户端。

    用法:
        client = LLMClient()
        response = client.chat(messages, tools)
    """

    def __init__(self) -> None:
        cfg = load_agent_config()
        self._model: str = cfg.get("model", "deepseek-chat")
        base_url: str = cfg.get("base_url", "https://api.deepseek.com")
        api_key_env: str = cfg.get("api_key_env", "DEEPSEEK_API_KEY")
        api_key: str = os.environ.get(api_key_env, "")

        if not api_key:
            raise RuntimeError(f"Agent 未配置 API key。请设置环境变量 {api_key_env}，例如: export {api_key_env}=sk-xxx")
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._temperature: float = float(cfg.get("temperature", 0.3))
        self._max_tokens: int = int(cfg.get("max_tokens", 4096))

    def chat(self, messages: list[dict], tools: list[dict] | None = None, timeout: float = 15.0):
        """发送消息到 LLM，返回原始 response 对象。

        response.choices[0].message 可能包含 content 或 tool_calls。
        """
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "timeout": timeout,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self._client.chat.completions.create(**kwargs)
