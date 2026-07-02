"""
Tests for the strategy registry and base class infrastructure.
"""

import pytest

from backend.strategy.base import BaseStrategy, calc_shares
from backend.strategy.registry import (
    _registry,
    all_strategies,
    get_strategy,
    list_strategies_metadata,
)


# ---------------------------------------------------------------------------
# calc_shares
# ---------------------------------------------------------------------------


class TestCalcShares:
    def test_basic(self):
        assert calc_shares(10000, 10) == 1000.0

    def test_rounds_down_to_integer(self):
        assert calc_shares(10000, 3) == 3333.0

    def test_zero_price_returns_zero(self):
        assert calc_shares(10000, 0) == 0.0

    def test_negative_price_returns_zero(self):
        assert calc_shares(10000, -5) == 0.0

    def test_cash_constraint_limits_shares(self):
        shares = calc_shares(100000, 10, cash_available=500)
        assert shares <= 50  # 500/10 = 50

    def test_cash_constraint_not_applied_when_none(self):
        shares = calc_shares(100000, 10)
        assert shares == 10000.0

    def test_small_target_less_than_one_share(self):
        shares = calc_shares(5, 100)
        assert shares == 0.0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_strategies_returns_at_least_three(self):
        assert len(all_strategies()) >= 3

    def test_get_known_strategy(self):
        cls = get_strategy("equal_weight")
        assert cls is not None
        assert cls.name == "equal_weight"
        assert cls.label == "动量轮动"

    def test_get_unknown_strategy_returns_none(self):
        assert get_strategy("nonexistent_strat") is None

    def test_each_registered_has_name(self):
        for cls in all_strategies():
            assert isinstance(cls.name, str)
            assert len(cls.name) > 0
            assert cls.name in _registry

    def test_list_metadata_returns_valid_schema(self):
        meta = list_strategies_metadata()
        assert isinstance(meta, list)
        for s in meta:
            assert "name" in s
            assert "label" in s
            assert "description" in s
            assert "color" in s
            assert isinstance(s["color"], str)
            assert s["color"].startswith("#")
            assert "params" in s
            assert isinstance(s["params"], dict)
            for pname, pmeta in s["params"].items():
                assert "type" in pmeta
                assert "default" in pmeta
                assert "label" in pmeta


# ---------------------------------------------------------------------------
# param_schema
# ---------------------------------------------------------------------------


class TestParamSchema:
    def test_equal_weight_has_three_params(self):
        cls = get_strategy("equal_weight")
        schema = cls.param_schema()
        assert "top_k" in schema
        assert "lookback" in schema
        assert "price_add" in schema
        assert schema["top_k"]["type"] == "int"
        assert schema["top_k"]["default"] == 3

    def test_vp_breakout_has_nine_params(self):
        cls = get_strategy("vp_breakout")
        schema = cls.param_schema()
        assert len(schema) >= 9

    def test_stop_loss_has_negative_range(self):
        cls = get_strategy("vp_breakout")
        schema = cls.param_schema()
        assert schema["stop_loss"]["min"] < 0
        assert schema["stop_loss"]["max"] < 0

    def test_param_schema_excludes_base_class_attrs(self):
        """name/label/description/color should NOT appear as tunable params."""
        cls = get_strategy("equal_weight")
        schema = cls.param_schema()
        assert "name" not in schema
        assert "label" not in schema
        assert "description" not in schema
        assert "color" not in schema


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------


class TestAutoRegistration:
    def test_subclass_auto_registers(self):
        class TempStrat(BaseStrategy):
            name = "temp_test_strat"
            label = "临时测试"
            description = "for testing"
            color = "#000000"

        try:
            registered = get_strategy("temp_test_strat")
            assert registered is TempStrat
            assert registered.label == "临时测试"
        finally:
            _registry.pop("temp_test_strat", None)

    def test_duplicate_name_raises(self):
        class DupA(BaseStrategy):
            name = "dup_test"
            label = "A"
            description = ""
            color = "#111"

        with pytest.raises(ValueError, match="策略名重复"):

            class DupB(BaseStrategy):  # noqa: F841
                name = "dup_test"
                label = "B"
                description = ""
                color = "#222"

        _registry.pop("dup_test", None)

    def test_missing_name_raises(self):
        with pytest.raises(TypeError, match="必须定义 `name`"):

            class BadStrat(BaseStrategy):  # noqa: F841
                label = "bad"
                description = ""
                color = "#333"
