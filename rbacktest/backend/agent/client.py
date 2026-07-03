"""
LLM 客户端 —— 封装 OpenAI 兼容 API 调用。

设计：
    - 只关心 messages + tools → response，不泄漏底层 provider 细节
    - 通过配置文件切换 DeepSeek / OpenAI / 本地模型
    - 不在这里写任何 Agent 逻辑
"""

from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI


def _load_agent_config() -> dict:
    """从 rbacktest.toml 加载 [agent] 配置节，缺失时使用默认值。"""
    config_path = Path(__file__).resolve().parent.parent.parent / "rbacktest.toml"
    cfg: dict = {}
    try:
        if config_path.exists():
            import tomllib

            raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
            cfg = raw.get("agent", {})
    except Exception:
        pass
    return cfg


class LLMClient:
    """OpenAI 兼容的 LLM 客户端。

    用法:
        client = LLMClient()
        response = client.chat(messages, tools)
    """

    def __init__(self) -> None:
        cfg = _load_agent_config()
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
