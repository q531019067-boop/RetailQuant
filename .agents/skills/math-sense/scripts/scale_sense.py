#!/usr/bin/env python3
"""
scale_sense.py — 数量感工具（数值→人类可感知的语言描述）

核心理念: 大模型无法直观感受"1000000"和"0.000001"的差异。
本脚本将数值翻译为带类比、参照物、比例语言的描述。

用法:
    python scale_sense.py --op "compare" --a 1000000 --b 1000 --label-a "服务器QPS" --label-b "家用路由器QPS"
    python scale_sense.py --op "order" --value 0.0000003 --unit "s"
    python scale_sense.py --op "proportion" --ratio 0.037
    python scale_sense.py --op "analogy" --value 150000 --unit "km"
    python scale_sense.py --op "convert" --value 60 --from-unit "fps" --to-unit "frame_ms"

支持的操作:
    compare, order, proportion, analogy, convert, anchors
"""

import sys, json, math, argparse


# ====================== 数量级参照知识库 ======================

SCALE_ANCHORS = {
    "length": {
        "unit": "m",
        "anchors": [
            (1e-15, "飞米", "原子核直径 (~1.7 fm)"),
            (1e-12, "皮米", "最小原子(氢)半径的1/25"),
            (1e-10, "埃", "单个原子直径 (~1 Å)"),
            (1e-9, "纳米", "DNA双螺旋宽度 (~2 nm)"),
            (1e-7, "0.1微米", "可见光最短波长 (紫光~400nm)"),
            (1e-6, "微米", "细菌大小 (~1-5 μm)"),
            (1e-4, "0.1毫米", "一张纸的厚度 (~0.1 mm)"),
            (1e-3, "毫米", "蚂蚁体长 (~3-5 mm)"),
            (1e-2, "厘米", "成年人大拇指宽度 (~2 cm)"),
            (1e-1, "10厘米=1分米", "智能手机宽度 (~7 cm)"),
            (1.0, "米", "成年人身高 (~1.7 m)"),
            (1e1, "10米", "三层楼房高度"),
            (1e2, "100米", "足球场长度 (~105 m)"),
            (1e3, "公里", "步行约12分钟的距离"),
            (1e4, "10公里", "马拉松的1/4"),
            (1e5, "100公里", "北京到天津的距离 (~120 km)"),
            (1e6, "1000公里", "北京到上海 (~1200 km)"),
            (1e7, "1万公里", "地球直径 (~12742 km)"),
            (3.84e8, "38万公里", "地球到月球的距离"),
            (1.5e11, "1.5亿公里", "地球到太阳的距离 (1 AU)"),
            (9.46e15, "1光年", "光走一年的距离"),
        ],
    },
    "time": {
        "unit": "s",
        "anchors": [
            (1e-24, "幺秒", "光穿过原子核的时间"),
            (1e-18, "阿秒", "电子绕原子核一周的时间"),
            (1e-15, "飞秒", "分子振动周期"),
            (1e-12, "皮秒", "晶体管开关时间 (~10 ps)"),
            (1e-9, "纳秒", "光走30厘米的时间 (~1 ns)"),
            (1e-6, "微秒", "闪电持续时间 (~30 μs)"),
            (1e-3, "毫秒", "相机快门 (~1-4 ms)；眨眼 (~100-400 ms)"),
            (1e-2, "10毫秒", "屏幕一帧 (60fps ~16.7ms)"),
            (1.0, "秒", "一次心跳 (~0.8 s)；说一个音节"),
            (6e1, "分钟", "泡一杯方便面 (3 min)；一首歌 (~4 min)"),
            (3.6e3, "小时", "一部电影 (~2 h)"),
            (8.64e4, "天", "地球自转一周"),
            (3.156e7, "年", "地球公转一周"),
            (1e9, "30年", "一代人的时间"),
            (1e11, "3000年", "人类文明史"),
            (4.5e17, "45亿年", "地球的年龄"),
            (1.38e10, "138亿年", "宇宙的年龄"),
        ],
    },
    "mass": {
        "unit": "kg",
        "anchors": [
            (1e-30, "电子质量", "约 9.1×10^{-31} kg"),
            (1e-27, "质子质量", "约 1.67×10^{-27} kg"),
            (1e-15, "飞克", "单个细胞的1/1000"),
            (1e-9, "纳克", "一颗粒子的质量"),
            (1e-6, "毫克", "一粒盐 (~0.1 mg)；一片雪花 (~1 mg)"),
            (1e-3, "克", "一枚回形针 (~1 g)；一张A4纸 (~5 g)"),
            (1e-1, "100克", "一个苹果 (~150 g)"),
            (1.0, "千克", "一瓶1L水 = 1 kg；笔记本电脑 (~2 kg)"),
            (1e1, "10千克", "一袋大米"),
            (1e2, "100千克", "成年男性 (~70 kg)；一头猪 (~150 kg)"),
            (1e3, "吨", "一辆小汽车 (~1.5 t)"),
            (1e5, "100吨", "一架波音737空重 (~40 t)；蓝鲸 (~150 t)"),
            (1e7, "万吨", "一艘航空母舰 (~10万吨)"),
            (1e12, "10亿吨", "一座小型山脉"),
            (5.97e24, "地球质量", "约 6×10^{24} kg"),
        ],
    },
    "data": {
        "unit": "byte",
        "anchors": [
            (1, "字节", "一个ASCII字符 (如 'A')"),
            (1e3, "KB", "一段短文 (~2 KB)"),
            (1e6, "MB", "一首MP3歌曲 (~4 MB)；一张照片 (~3-10 MB)"),
            (1e9, "GB", "一部高清电影 (~2-5 GB)；一本电子书 (~1 MB)"),
            (1e12, "TB", "个人硬盘容量 (~1-4 TB)"),
            (1e15, "PB", "大型数据中心 (~数十 PB)"),
            (1e18, "EB", "全球互联网年流量 (~数 ZB)"),
        ],
    },
    "game_damage": {
        "unit": "伤害值",
        "anchors": [
            (1, "1点", "挠痒痒——可以被忽略"),
            (1e1, "10点", "轻轻一拳——对新手怪有点感觉"),
            (1e2, "100点", "认真一击——小怪掉半管血"),
            (1e3, "1000点", "暴击——同级怪直接秒杀"),
            (1e4, "1万点", "大招伤害——BOSS都扛不住"),
            (1e5, "10万点", "核弹级——满配神装才能打出"),
            (1e6, "100万点", "数值膨胀——游戏后期或页游风格"),
        ],
    },
    "game_gold": {
        "unit": "金币",
        "anchors": [
            (1, "1金币", "打死一只新手小怪"),
            (1e1, "10金币", "回城卷轴的钱"),
            (1e2, "100金币", "一瓶中级药水"),
            (1e3, "1000金币=1K", "一件蓝装/低级强化"),
            (1e4, "1万金币=10K", "一件紫装/中级宝石"),
            (1e5, "10万金币", "一件橙装/高级坐骑"),
            (1e6, "100万金币=1M", "服务器顶级装备"),
            (1e7, "1000万金币", "全服首富级别"),
        ],
    },
    "game_level": {
        "unit": "级",
        "anchors": [
            (1, "1级", "刚出新手村"),
            (1e1, "10级", "掌握了基础技能，能独立打怪"),
            (2e1, "20级", "解锁核心玩法，组队副本起步"),
            (5e1, "50级", "中坚力量，可挑战大多数内容"),
            (7e1, "70级", "服务器主流梯队"),
            (1e2, "100级=满级", "毕业状态，追求装备和排名"),
        ],
    },
}

# 通用数量级形容词
MAGNITUDE_ADJECTIVES = [
    (1e-12, "微乎其微——几乎无法测量"),
    (1e-9, "极其微小——纳米级别"),
    (1e-6, "非常小——百万分之一"),
    (1e-3, "很小——千分之一"),
    (1e-2, "较小——百分之一"),
    (1e-1, "偏小——十分之一"),
    (1.0, ""),
    (1e1, "较大——十倍于基准"),
    (1e2, "很大——百倍于基准"),
    (1e3, "非常大——千倍于基准"),
    (1e6, "巨大——百万倍于基准"),
    (1e9, "天文级别——十亿倍于基准"),
    (1e12, "难以想象——万亿倍于基准"),
]

# 比例语言
PROPORTION_PHRASES = [
    (0.001, "千分之一，几乎为零"),
    (0.01, "百分之一，微小的比例"),
    (0.05, "二十分之一，非常低的概率"),
    (0.1, "十分之一，显著但不高"),
    (0.2, "五分之一，每五个中有一个"),
    (0.25, "四分之一，每四个中有一个"),
    (0.333, "约三分之一，常见的小比例"),
    (0.5, "一半，五五开"),
    (0.667, "约三分之二，大多数"),
    (0.75, "四分之三，绝大多数"),
    (0.9, "十分之九，几乎所有"),
    (0.95, "二十分之十九，极其显著"),
    (0.99, "百分之九十九，几乎确定"),
    (0.999, "千分之九百九十九，接近必然"),
]


# ====================== 操作实现 ======================


def _find_nearest_anchors(value, anchors):
    """找到最接近的上下锚点"""
    below, above = None, None
    for v, name, analogy in anchors:
        if v <= value:
            below = (v, name, analogy)
        if v >= value and above is None:
            above = (v, name, analogy)
            break
    return below, above


def _describe_magnitude(ratio):
    """描述一个比例的数量级"""
    if ratio == 0:
        return "完全相等"
    if ratio == 1:
        return "完全相同"
    abs_log = math.log10(abs(math.log(ratio))) if ratio > 0 and ratio != 1 else 0
    for threshold, adj in MAGNITUDE_ADJECTIVES:
        if ratio >= threshold:
            return adj
    return ""


def _proportion_phrase(ratio):
    """将比例转为自然语言"""
    if ratio <= 0:
        return "为零"
    if ratio >= 1:
        return "为全部 (100%)"
    best = "约 {:.1%}".format(ratio)
    for threshold, phrase in PROPORTION_PHRASES:
        if abs(ratio - threshold) < 0.02:
            return phrase
        if abs(ratio - threshold) < 0.05:
            return f"接近{phrase}"
    # 用分数近似
    for denom in [2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 50, 100]:
        num = round(ratio * denom)
        if abs(num / denom - ratio) < 0.01:
            return f"约{num}/{denom} (≈{ratio * 100:.1f}%)"
    return best


def op_order(value, unit=None, category=None):
    """数量级分析"""
    # 找匹配的类别
    cat_data = None
    if category and category in SCALE_ANCHORS:
        cat_data = SCALE_ANCHORS[category]
    elif unit:
        for cat, data in SCALE_ANCHORS.items():
            if data["unit"] == unit or unit in cat:
                cat_data = data
                break

    result = {
        "value": value,
        "scientific": f"{value:.6e}",
        "order_of_magnitude": int(math.floor(math.log10(abs(value)))) if value != 0 else None,
    }

    if cat_data:
        below, above = _find_nearest_anchors(value, cat_data["anchors"])
        if below:
            result["below_anchor"] = {"value": below[0], "name": below[1], "analogy": below[2]}
        if above:
            result["above_anchor"] = {"value": above[0], "name": above[1], "analogy": above[2]}

        # 生成描述
        parts = []
        parts.append(f"{value:.6g} {cat_data['unit']}")
        if below and above:
            ratio_to_below = value / below[0] if below[0] > 0 else float("inf")
            parts.append(f"介于「{below[1]}」({below[2]})和「{above[1]}」({above[2]})之间。")
            if 0.1 < ratio_to_below < 10:
                parts.append(f"大约是{below[1]}的{ratio_to_below:.1f}倍。")
        elif below:
            parts.append(f"大于「{below[1]}」({below[2]})。")
        elif above:
            parts.append(f"小于「{above[1]}」({above[2]})。")
        result["description"] = "".join(parts)

    return result


def op_compare(a, b, label_a="A", label_b="B", unit=None):
    """比较两个量，生成比例描述"""
    if b == 0:
        return {"error": "除数不能为零"}
    ratio = a / b
    diff = a - b
    pct_diff = (a - b) / abs(b) * 100 if b != 0 else float("inf")

    # 数量级差异
    if ratio >= 1:
        times = ratio
        order_diff = int(math.floor(math.log10(ratio))) if ratio > 0 else 0
    else:
        times = 1 / ratio
        order_diff = -int(math.floor(math.log10(abs(ratio)))) if ratio > 0 else 0

    # 生成描述
    parts = []
    if abs(ratio - 1) < 0.001:
        parts.append(f"{label_a} 与 {label_b} 几乎相等（差异<0.1%）。")
    elif ratio > 1:
        if ratio < 2:
            parts.append(f"{label_a} 比 {label_b} 大约 {ratio:.1f} 倍（超出 {pct_diff:.1f}%）。")
        elif ratio < 10:
            parts.append(f"{label_a} 是 {label_b} 的约 {ratio:.1f} 倍。")
        elif ratio < 1000:
            parts.append(f"{label_a} 是 {label_b} 的 {int(ratio)} 倍——相差两个数量级。")
        else:
            parts.append(f"{label_a} 是 {label_b} 的 {ratio:.2e} 倍——相差 {order_diff} 个数量级。")
        parts.append(f"可以理解为：{label_b} 在 {label_a} 面前，相当于「{_describe_magnitude(ratio)}」。")
    else:
        inv = 1 / ratio
        if inv < 10:
            parts.append(f"{label_a} 仅为 {label_b} 的 {ratio * 100:.1f}%（约 1/{inv:.1f}）。")
        else:
            parts.append(f"{label_a} 仅为 {label_b} 的 {ratio:.2e}——相差 {order_diff} 个数量级。")
        parts.append(f"可以理解为：{label_a} 在 {label_b} 面前，相当于「{_describe_magnitude(ratio)}」。")

    return {
        "a": a,
        "b": b,
        "label_a": label_a,
        "label_b": label_b,
        "ratio": ratio,
        "times": times if ratio >= 1 else 1 / ratio,
        "pct_diff": pct_diff,
        "order_diff": order_diff,
        "description": "".join(parts),
    }


def op_proportion(ratio):
    """将比例/百分比转为自然语言"""
    phrase = _proportion_phrase(ratio)
    # 附加语境
    context = ""
    if ratio < 0.001:
        context = (
            "在统计学中，这个概率可以被视为'几乎不可能发生'。如果每天做一次，平均需要约 {:.0f} 年才会遇到一次。".format(
                1 / (ratio * 365) if ratio > 0 else float("inf")
            )
        )
    elif ratio < 0.01:
        context = "大约相当于掷硬币连续 {:.0f} 次正面的概率。".format(-math.log2(ratio) if ratio > 0 else 0)
    elif ratio < 0.1:
        context = "在10次尝试中，期望约1次成功。"
    elif ratio < 0.5:
        context = "少于一半的概率。"
    elif ratio < 0.9:
        context = "大概率事件，但仍不可掉以轻心。"
    else:
        context = "几乎确定会发生。"

    return {
        "ratio": ratio,
        "percentage": f"{ratio * 100:.2f}%",
        "phrase": phrase,
        "context": context,
    }


def op_analogy(value, unit=None, category=None):
    """找到最接近的人类可感知参照物"""
    cat_data = None
    if category and category in SCALE_ANCHORS:
        cat_data = SCALE_ANCHORS[category]
    elif unit:
        for cat, data in SCALE_ANCHORS.items():
            if data.get("unit", "") == unit or unit in cat:
                cat_data = data
                break

    if not cat_data:
        return {"error": f"未找到类别 '{category or unit}'，可用: {list(SCALE_ANCHORS.keys())}"}

    # 找到最接近的锚点
    anchors = cat_data["anchors"]
    closest = min(anchors, key=lambda a: abs(math.log10(value / a[0])) if a[0] > 0 and value > 0 else float("inf"))
    ratio = value / closest[0] if closest[0] > 0 else float("inf")

    parts = []
    parts.append(f"{value:.4g} {cat_data['unit']} —— ")
    if abs(ratio - 1) < 0.05:
        parts.append(f"几乎正好是「{closest[1]}」：{closest[2]}。")
    elif ratio > 1:
        parts.append(f"大约是「{closest[1]}」的 {ratio:.1f} 倍。参照：{closest[1]} 对应 {closest[2]}。")
    else:
        parts.append(f"大约是「{closest[1]}」的 1/{1 / ratio:.1f}。参照：{closest[1]} 对应 {closest[2]}。")

    return {
        "value": value,
        "unit": cat_data["unit"],
        "closest_anchor": {"value": closest[0], "name": closest[1], "analogy": closest[2]},
        "ratio": ratio,
        "description": "".join(parts),
    }


def op_convert(value, from_unit, to_unit):
    """单位转换（常用游戏/物理单位）"""
    # 常用转换表
    CONVERSIONS = {
        ("fps", "frame_ms"): lambda v: 1000 / v if v > 0 else float("inf"),
        ("frame_ms", "fps"): lambda v: 1000 / v if v > 0 else float("inf"),
        ("m", "km"): lambda v: v / 1000,
        ("km", "m"): lambda v: v * 1000,
        ("s", "ms"): lambda v: v * 1000,
        ("ms", "s"): lambda v: v / 1000,
        ("min", "s"): lambda v: v * 60,
        ("h", "min"): lambda v: v * 60,
        ("day", "h"): lambda v: v * 24,
        ("kg", "g"): lambda v: v * 1000,
        ("g", "mg"): lambda v: v * 1000,
        ("GB", "MB"): lambda v: v * 1024,
        ("MB", "KB"): lambda v: v * 1024,
        ("rad", "deg"): lambda v: v * 180 / math.pi,
        ("deg", "rad"): lambda v: v * math.pi / 180,
        ("percent", "ratio"): lambda v: v / 100,
        ("ratio", "percent"): lambda v: v * 100,
    }

    key = (from_unit, to_unit)
    if key in CONVERSIONS:
        result_val = CONVERSIONS[key](value)
        return {
            "from": {"value": value, "unit": from_unit},
            "to": {"value": result_val, "unit": to_unit},
            "formula": f"1 {from_unit} → {CONVERSIONS[key](1):.6g} {to_unit}",
        }
    return {
        "error": f"不支持的转换: {from_unit} → {to_unit}。支持: fps↔frame_ms, m↔km, s↔ms↔min↔h, kg↔g, GB↔MB, rad↔deg, percent↔ratio"
    }


def op_anchors(category=None):
    """列出可用的参照类别"""
    if category:
        return SCALE_ANCHORS.get(category, {"error": f"未知类别: {category}"})
    return {"categories": {k: {"unit": v["unit"], "anchor_count": len(v["anchors"])} for k, v in SCALE_ANCHORS.items()}}


OPERATIONS = {
    "order": op_order,
    "compare": op_compare,
    "proportion": op_proportion,
    "analogy": op_analogy,
    "convert": op_convert,
    "anchors": op_anchors,
}


def main():
    parser = argparse.ArgumentParser(
        description="数量感工具 — 数值→人类可感知的语言描述",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scale_sense.py --op "compare" --a 1000000 --b 1000 --label-a "服务器QPS" --label-b "路由器QPS"
  python scale_sense.py --op "order" --value 0.0000003 --category "time"
  python scale_sense.py --op "proportion" --ratio 0.037
  python scale_sense.py --op "analogy" --value 150000 --category "length"
  python scale_sense.py --op "convert" --value 60 --from-unit "fps" --to-unit "frame_ms"
  python scale_sense.py --op "anchors"
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--value", type=float, help="数值")
    parser.add_argument("--a", type=float, help="比较对象A")
    parser.add_argument("--b", type=float, help="比较对象B")
    parser.add_argument("--label-a", default="A", help="对象A的标签")
    parser.add_argument("--label-b", default="B", help="对象B的标签")
    parser.add_argument("--ratio", type=float, help="比例值 (0-1)")
    parser.add_argument("--unit", help="单位")
    parser.add_argument("--category", "-c", help="参照类别: length/time/mass/data/game_damage/game_gold/game_level")
    parser.add_argument("--from-unit", help="源单位")
    parser.add_argument("--to-unit", help="目标单位")
    parser.add_argument("--compact", action="store_true", help="紧凑输出")
    parser.add_argument("json_input", nargs="?", help="JSON 输入")

    args = parser.parse_args()
    input_data = {}
    if args.json_input:
        input_data = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            input_data = json.loads(raw)

    op = args.op or input_data.get("op", "")
    if not op or op not in OPERATIONS:
        print(json.dumps({"ok": False, "error": f"不支持: {op}，可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if op == "order":
            kwargs["value"] = args.value or input_data.get("value", 0)
            kwargs["unit"] = args.unit or input_data.get("unit")
            kwargs["category"] = args.category or input_data.get("category")
        elif op == "compare":
            kwargs["a"] = args.a if args.a is not None else input_data.get("a", 0)
            kwargs["b"] = args.b if args.b is not None else input_data.get("b", 0)
            kwargs["label_a"] = args.label_a or input_data.get("label_a", "A")
            kwargs["label_b"] = args.label_b or input_data.get("label_b", "B")
        elif op == "proportion":
            kwargs["ratio"] = args.ratio if args.ratio is not None else input_data.get("ratio", 0)
        elif op == "analogy":
            kwargs["value"] = args.value or input_data.get("value", 0)
            kwargs["unit"] = args.unit or input_data.get("unit")
            kwargs["category"] = args.category or input_data.get("category")
        elif op == "convert":
            kwargs["value"] = args.value or input_data.get("value", 0)
            kwargs["from_unit"] = args.from_unit or input_data.get("from_unit", "")
            kwargs["to_unit"] = args.to_unit or input_data.get("to_unit", "")
        elif op == "anchors":
            kwargs["category"] = args.category or input_data.get("category")

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
