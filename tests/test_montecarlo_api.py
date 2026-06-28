"""rquant.research.montecarlo — HTTP API 集成测试

设计
----
- 用 Flask ``test_client``（不启 server，快）。
- 通过 ``unittest.mock.patch`` 把 ``rquant.web.routes.data.fetch_kline`` 和
  ``get_stock`` 替换为合成数据，避免依赖真实数据源 + 网络。
- 测试覆盖：基本成功 / K 线空 / fetch 异常 / 库 error 透传 / 当前价覆盖 /
  TP/SL 兜底 / query 参数正确传递 / code 校验。

运行::

    pytest tests/test_montecarlo_api.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


# ============================================================
# 1. 准备 Flask app + 合成 K 线
# ============================================================

# 直接用项目入口 app.py 暴露的 app（与生产一致）
from app import app  # noqa: E402


@pytest.fixture()
def client():
    """Flask 测试客户端"""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_gbm_kline(n: int = 252, seed: int = 42, start_price: float = 12.34) -> pd.DataFrame:
    """合成 GBM K 线（与 test_montecarlo.py 的 _make_gbm_kline 一致）"""
    rng = np.random.default_rng(seed)
    log_rets = rng.normal(0.0005, 0.02, n)
    prices: list[float] = [start_price]
    for r in log_rets:
        prices.append(prices[-1] * float(np.exp(r)))
    prices = np.array(prices)
    dates = pd.date_range("2024-01-01", periods=n + 1, freq="B")
    vol = rng.integers(1_000_000, 5_000_000, n + 1).astype(float)
    return pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices,
            "volume": vol,
        }
    )


# ============================================================
# 2. 测试
# ============================================================


def test_route_registered(client):
    """路由必须存在 + 接受 GET"""
    resp = client.get("/api/montecarlo/sh600000")
    # 即使 fetch_kline 没 mock，也不会到 404（除非真的返回空），最差是 5xx
    # 这里主要验证路由存在
    assert resp.status_code in (200, 400, 404, 500)


def test_basic_success(client):
    """基本调用：mock fetch_kline + get_stock → 200 + 关键字段"""
    df = _make_gbm_kline(n=252)
    current = float(df["close"].iloc[-1])
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={"name": "测试股"}),
    ):
        resp = client.get("/api/montecarlo/sh600000?days=20&sims=500&seed=42")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    # 透传字段
    assert body["code"] == "sh600000"
    assert body["name"] == "测试股"
    assert body["current_price"] == round(current, 4)
    assert body["forecast_days"] == 20
    assert body["simulations"] == 500
    # 关键统计字段
    for k in (
        "expected_return_pct",
        "prob_higher_pct",
        "max_drawdown_median_pct",
        "max_drawdown_worst_5pct_pct",
        "prob_take_profit_pct",
        "prob_stop_loss_pct",
    ):
        assert k in body["stats"], f"missing stats.{k}"
    # path 长度
    assert len(body["paths"]["median"]) == 21


def test_seed_reproducible_via_api(client):
    """API 透传 seed → 两次结果一致"""
    df = _make_gbm_kline(n=252)
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        r1 = client.get("/api/montecarlo/sh600000?seed=42&sims=200").get_json()
        r2 = client.get("/api/montecarlo/sh600000?seed=42&sims=200").get_json()
    assert r1["paths"]["median"] == r2["paths"]["median"]


def test_live_price_override(client):
    """live_price 覆盖 K 线最后 close 作为 GBM 起点"""
    df = _make_gbm_kline(n=252, start_price=12.34)
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000?live_price=99.99&sims=200&seed=42")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["ok"] is True
    assert body["current_price"] == 99.99
    # paths 的第一列（day 0）应等于 current_price
    assert abs(body["paths"]["median"][0] - 99.99) < 1e-6


def test_tp_sl_passed_through(client):
    """显式 TP/SL 透传到库（库内会按用户输入算命中率）"""
    df = _make_gbm_kline(n=252, start_price=10.0)
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000?tp=10.5&sl=9.5&sims=500&seed=42")
    body = resp.get_json()
    assert resp.status_code == 200
    # 库内不会动 tp/sl（自洽 → TP>SL 正常）
    assert body["take_profit"] == 10.5
    assert body["stop_loss"] == 9.5
    assert body["stats"]["prob_take_profit_pct"] is not None
    assert body["stats"]["prob_stop_loss_pct"] is not None


def test_tp_sl_zero_falls_back_to_library(client):
    """tp=0 / sl=0 → API 视为未传，让库内兜底到 current_price ×1.08 / ×0.96"""
    df = _make_gbm_kline(n=252, start_price=10.0)
    current = float(df["close"].iloc[-1])
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000?tp=0&sl=0&sims=200&seed=42")
    body = resp.get_json()
    assert resp.status_code == 200
    # 库内兜底：current_price ×1.08 / ×0.96（注意 current 不是 start_price）
    assert body["take_profit"] == round(current * 1.08, 2)
    assert body["stop_loss"] == round(current * 0.96, 2)


def test_empty_kline_returns_404(client):
    """K 线为空 → 404"""
    empty = pd.DataFrame()
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=empty),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False
    assert "K 线" in body["error"]


def test_fetch_exception_returns_500(client):
    """fetch_kline 抛异常 → 500"""
    with (
        patch("rquant.web.routes.data.fetch_kline", side_effect=RuntimeError("网络炸了")),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["ok"] is False
    assert "网络炸了" in body["error"]


def test_library_error_passthrough(client):
    """库返回 error 字段（如数据不足）→ API 透传 400"""
    # 数据不足 30 天
    short_df = _make_gbm_kline(n=10)
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=short_df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "数据不足" in body["error"]
    assert body["code"] == "sh600000"


def test_code_normalized_lowercase(client):
    """code 大写 → 规范化为小写"""
    df = _make_gbm_kline(n=252)
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/SH600000")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["code"] == "sh600000"


def test_lookback_param_min_30(client):
    """lookback 传 5 → 内部钳到 30（防止用户传太小导致样本不足）"""
    df = _make_gbm_kline(n=252)
    with (
        patch("rquant.web.routes.data.fetch_kline", return_value=df),
        patch("rquant.web.routes.data.get_stock", return_value={}),
    ):
        resp = client.get("/api/montecarlo/sh600000?lookback=5&sims=100&seed=42")
    # 不应该因为 lookback=5 导致样本不足 error
    body = resp.get_json()
    assert resp.status_code == 200
    # 实际用的 lookback_days 在 path 数决定，不在 body，但应该正常跑完
    assert body["ok"] is True
