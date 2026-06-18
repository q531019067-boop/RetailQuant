#!/usr/bin/env python3
"""
spatial_sense.py — 空间推理工具（坐标系/旋转/方位/参考系）

核心理念: 大模型对方向、旋转、坐标系变换缺乏直观感受。
本脚本将空间关系转换为多维度精确描述和数值结果。

用法:
    python spatial_sense.py --op "describe_position" --x 10 --y 5 --z 3 --observer "0,0,0"
    python spatial_sense.py --op "bearing_to_words" --angle 135
    python spatial_sense.py --op "words_to_bearing" --desc "东北偏北30度"
    python spatial_sense.py --op "transform" --point "5,0,0" --from-frame "world" --to-frame "camera" --camera-pos "10,5,3" --camera-yaw 45
    python spatial_sense.py --op "relative" --a "0,0,0" --b "10,0,0" --a-facing 90

支持的操作:
    describe_position, bearing_to_words, words_to_bearing,
    transform, relative, coordinate_convert
"""

import sys, json, math, argparse, re

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _parse_vec(s):
    if isinstance(s, (list, tuple)):
        return [float(v) for v in s[:3]]
    if isinstance(s, str):
        s = s.strip()
        if s.startswith("["):
            return [float(v) for v in json.loads(s)[:3]]
        return [float(v.strip()) for v in s.split(",")[:3]]
    return [0.0, 0.0, 0.0]


# ====================== 方位描述 ======================

BEARING_NAMES = [
    (0, "正北"),
    (22.5, "北东北"),
    (45, "东北"),
    (67.5, "东东北"),
    (90, "正东"),
    (112.5, "东东南"),
    (135, "东南"),
    (157.5, "南东南"),
    (180, "正南"),
    (202.5, "南西南"),
    (225, "西南"),
    (247.5, "西西南"),
    (270, "正西"),
    (292.5, "西西北"),
    (315, "西北"),
    (337.5, "北西北"),
    (360, "正北"),
]

BEARING_WORDS_PATTERNS = [
    (r"正北", 0),
    (r"北东北|北偏东", 22.5),
    (r"东北", 45),
    (r"东东北|东偏北", 67.5),
    (r"正东", 90),
    (r"东东南|东偏南", 112.5),
    (r"东南", 135),
    (r"南东南|南偏东", 157.5),
    (r"正南", 180),
    (r"南西南|南偏西", 202.5),
    (r"西南", 225),
    (r"西西南|西偏南", 247.5),
    (r"正西", 270),
    (r"西西北|西偏北", 292.5),
    (r"西北", 315),
    (r"北西北|北偏西", 337.5),
]


def op_bearing_to_words(angle_deg):
    """角度 → 方位语言"""
    angle = angle_deg % 360
    # 找到最近的方位名
    closest = min(BEARING_NAMES, key=lambda x: abs(x[0] - angle))
    name = closest[1]
    diff = angle - closest[0]
    # 精确描述
    if abs(diff) < 0.5:
        desc = name
    elif diff > 0:
        desc = f"{name}偏{'东' if angle < 180 else '西'}{abs(diff):.0f}度"
    else:
        desc = f"{name}偏{'西' if angle < 180 else '东'}{abs(diff):.0f}度"

    return {
        "angle_deg": angle_deg,
        "angle_rad": math.radians(angle_deg),
        "closest_cardinal": name,
        "description": desc,
        "full_description": f"{desc}（{angle_deg:.1f}°）",
    }


def op_words_to_bearing(desc):
    """方位语言 → 角度"""
    # 先尝试精确角度
    m = re.search(r"(\d+(?:\.\d+)?)\s*度", desc)
    if m:
        return {"description": desc, "angle_deg": float(m.group(1)), "confidence": "exact"}

    # 匹配方位词
    for pattern, base_angle in BEARING_WORDS_PATTERNS:
        if re.search(pattern, desc):
            # 检查是否有偏移
            offset = 0
            om = re.search(r"偏(东|西|南|北)\s*(\d+)\s*度", desc)
            if om:
                direction = om.group(1)
                offset = float(om.group(2))
                if direction in ("西", "北"):
                    offset = -offset
            angle = (base_angle + offset) % 360
            return {
                "description": desc,
                "angle_deg": angle,
                "base": base_angle,
                "offset": offset,
                "confidence": "approximate",
            }

    return {
        "description": desc,
        "angle_deg": None,
        "confidence": "unknown",
        "note": "无法解析，请使用'东北偏东30度'或直接给出角度值",
    }


# ====================== 位置描述 ======================


def op_describe_position(x, y, z, observer=None):
    """描述一个点相对于观察者的位置"""
    if observer:
        ox, oy, oz = _parse_vec(observer) if isinstance(observer, str) else observer[:3]
        dx, dy, dz = x - ox, y - oy, z - oz
    else:
        ox, oy, oz = 0, 0, 0
        dx, dy, dz = x, y, z

    # 水平距离和方向
    horiz_dist = math.sqrt(dx**2 + dy**2)
    horiz_angle = math.degrees(math.atan2(dx, dy)) % 360

    # 3D距离
    total_dist = math.sqrt(dx**2 + dy**2 + dz**2)

    # 仰角
    elev_angle = math.degrees(math.atan2(dz, horiz_dist)) if horiz_dist > 0 else (90 if dz > 0 else -90)

    # 方位语言
    bearing = op_bearing_to_words(horiz_angle)

    # 生成描述
    parts = []
    parts.append(f"水平距离 {horiz_dist:.2f}，方位 {bearing['description']}（{horiz_angle:.1f}°）")
    parts.append(f"直线距离 {total_dist:.2f}")
    if abs(dz) < 0.01:
        parts.append("在同一水平面上")
    elif dz > 0:
        parts.append(f"在上方 {dz:.2f}，仰角 {elev_angle:.1f}°")
    else:
        parts.append(f"在下方 {abs(dz):.2f}，俯角 {abs(elev_angle):.1f}°")

    return {
        "point": [x, y, z],
        "observer": [ox, oy, oz] if observer else None,
        "relative": {"dx": dx, "dy": dy, "dz": dz},
        "horizontal_distance": horiz_dist,
        "total_distance": total_dist,
        "horizontal_angle_deg": horiz_angle,
        "elevation_angle_deg": elev_angle,
        "bearing_words": bearing["description"],
        "description": "；".join(parts),
    }


# ====================== 坐标系转换 ======================


def op_coordinate_convert(x, y, z, from_sys, to_sys):
    """笛卡尔 ↔ 球坐标 ↔ 柱坐标 转换"""
    result = {"input": {"x": x, "y": y, "z": z, "system": from_sys}}

    if from_sys == "cartesian" and to_sys == "spherical":
        r = math.sqrt(x**2 + y**2 + z**2)
        theta = math.degrees(math.atan2(y, x)) % 360
        phi = math.degrees(math.acos(z / r)) if r > 0 else 0
        result["output"] = {"r": r, "theta_deg": theta, "phi_deg": phi, "system": "spherical"}
        result["description"] = f"球坐标: r={r:.3f}, θ(方位)={theta:.1f}°, φ(极角)={phi:.1f}°"

    elif from_sys == "spherical" and to_sys == "cartesian":
        r, theta, phi = x, y, z
        theta_rad = math.radians(theta)
        phi_rad = math.radians(phi)
        cx = r * math.sin(phi_rad) * math.cos(theta_rad)
        cy = r * math.sin(phi_rad) * math.sin(theta_rad)
        cz = r * math.cos(phi_rad)
        result["output"] = {"x": cx, "y": cy, "z": cz, "system": "cartesian"}
        result["description"] = f"笛卡尔: ({cx:.3f}, {cy:.3f}, {cz:.3f})"

    elif from_sys == "cartesian" and to_sys == "cylindrical":
        rho = math.sqrt(x**2 + y**2)
        phi = math.degrees(math.atan2(y, x)) % 360
        result["output"] = {"rho": rho, "phi_deg": phi, "z": z, "system": "cylindrical"}
        result["description"] = f"柱坐标: ρ={rho:.3f}, φ={phi:.1f}°, z={z:.3f}"

    elif from_sys == "cylindrical" and to_sys == "cartesian":
        rho, phi, cz = x, y, z
        phi_rad = math.radians(phi)
        result["output"] = {"x": rho * math.cos(phi_rad), "y": rho * math.sin(phi_rad), "z": cz, "system": "cartesian"}
        result["description"] = f"笛卡尔: ({result['output']['x']:.3f}, {result['output']['y']:.3f}, {cz:.3f})"

    else:
        result["error"] = f"不支持的转换: {from_sys} → {to_sys}"

    return result


# ====================== 参考系变换 ======================


def op_transform(point_str, from_frame, to_frame, camera_pos=None, camera_yaw=0, camera_pitch=0):
    """参考系变换：将点从一个参考系变换到另一个"""
    px, py, pz = _parse_vec(point_str)
    result = {"point": [px, py, pz], "from": from_frame, "to": to_frame}

    if from_frame == "world" and to_frame == "camera" and camera_pos:
        cx, cy, cz = _parse_vec(camera_pos)
        # 平移到相机位置
        dx, dy, dz = px - cx, py - cy, pz - cz
        # 旋转到相机朝向
        yaw_rad = math.radians(-camera_yaw)
        pitch_rad = math.radians(-camera_pitch)
        # 先绕Z轴（偏航），再绕X轴（俯仰）
        rx = dx * math.cos(yaw_rad) + dy * math.sin(yaw_rad)
        ry = -dx * math.sin(yaw_rad) + dy * math.cos(yaw_rad)
        rz = dz
        # 俯仰
        rx2 = rx
        ry2 = ry * math.cos(pitch_rad) - rz * math.sin(pitch_rad)
        rz2 = ry * math.sin(pitch_rad) + rz * math.cos(pitch_rad)
        result["camera_space"] = [rx2, ry2, rz2]
        result["description"] = (
            f"在世界空间中点({px:.1f},{py:.1f},{pz:.1f})，"
            f"相对于相机（位置{camera_pos}，偏航{camera_yaw}°），"
            f"在相机空间中为：前方={ry2:.2f}，右侧={rx2:.2f}，上方={rz2:.2f}"
        )
        # 判断是否在视野内（假设FOV=90°）
        if ry2 > 0:
            half_fov = 45
            h_angle = math.degrees(math.atan2(rx2, ry2))
            v_angle = math.degrees(math.atan2(rz2, ry2))
            in_vision = abs(h_angle) < half_fov and abs(v_angle) < half_fov
            result["in_camera_view"] = in_vision
            result["screen_offset"] = f"水平偏移{h_angle:.1f}°，垂直偏移{v_angle:.1f}°"
        else:
            result["in_camera_view"] = False
            result["screen_offset"] = "在相机后方，不可见"

    elif from_frame == "camera" and to_frame == "world" and camera_pos:
        # 逆变换
        cx, cy, cz = _parse_vec(camera_pos)
        yaw_rad = math.radians(camera_yaw)
        pitch_rad = math.radians(camera_pitch)
        # 逆俯仰
        ry = py * math.cos(-pitch_rad) + pz * math.sin(-pitch_rad)
        rz = -py * math.sin(-pitch_rad) + pz * math.cos(-pitch_rad)
        # 逆偏航
        rx = px * math.cos(-yaw_rad) + ry * math.sin(-yaw_rad)
        wy = -px * math.sin(-yaw_rad) + ry * math.cos(-yaw_rad)
        wx, wy, wz = rx + cx, wy + cy, rz + cz
        result["world_space"] = [wx, wy, wz]
        result["description"] = f"相机空间({px:.1f},{py:.1f},{pz:.1f}) → 世界空间({wx:.1f},{wy:.1f},{wz:.1f})"

    else:
        result["note"] = "目前支持 world↔camera 变换，需提供 camera_pos, camera_yaw"

    return result


# ====================== 相对关系 ======================


def op_relative(a_str, b_str, a_facing=0):
    """两个物体之间的相对位置/角度/方位关系"""
    ax, ay, az = _parse_vec(a_str)
    bx, by, bz = _parse_vec(b_str)
    dx, dy, dz = bx - ax, by - ay, bz - az
    dist = math.sqrt(dx**2 + dy**2 + dz**2)
    horiz_dist = math.sqrt(dx**2 + dy**2)

    # B相对于A的方位角（世界坐标系）
    world_bearing = math.degrees(math.atan2(dx, dy)) % 360

    # B相对于A的朝向的方位角（A的局部坐标系）
    local_bearing = (world_bearing - a_facing) % 360

    # 方位语言
    world_words = op_bearing_to_words(world_bearing)
    local_words = op_bearing_to_words(local_bearing)

    # A的视野判断
    fwd = a_facing
    half_fov = 60  # 假设120度视野
    angle_from_fwd = min(abs(local_bearing - 0), 360 - abs(local_bearing - 0))
    in_fov = angle_from_fwd < half_fov

    # 左右前后描述
    if angle_from_fwd < 30:
        lr = "正前方"
    elif local_bearing < 180:
        lr = f"右前方{angle_from_fwd:.0f}度"
    else:
        lr = f"左前方{angle_from_fwd:.0f}度"

    result = {
        "a": [ax, ay, az],
        "b": [bx, by, bz],
        "a_facing_deg": a_facing,
        "distance": {"total": dist, "horizontal": horiz_dist, "vertical": dz},
        "world_bearing": {"angle": world_bearing, "words": world_words["description"]},
        "local_bearing": {"angle": local_bearing, "words": local_words["description"]},
        "in_a_field_of_view": in_fov,
        "relative_position": lr,
    }

    # 完整描述
    parts = [f"B在A的{local_words['description']}方向（世界方位{world_bearing:.0f}°）"]
    parts.append(f"水平距离{horiz_dist:.2f}，直线距离{dist:.2f}")
    if abs(dz) > 0.01:
        parts.append(f"{'上方' if dz > 0 else '下方'}{abs(dz):.2f}")
    parts.append(f"A面朝{a_facing}°，B相对于A朝向偏移{local_bearing:.0f}°，位于{lr}")
    parts.append(f"在A的视野{'内' if in_fov else '外'}（假设{A.get('fov', 120)}°视野）")
    result["description"] = "；".join(parts)

    return result


# ====================== 语言 → 数学 ======================


def op_describe_to_math(description):
    """将空间关系的语言描述转换为精确数学表达"""
    result = {"description": description, "extracted": {}}

    # 提取距离
    dist_m = re.search(r"(\d+(?:\.\d+)?)\s*米", description)
    if dist_m:
        result["extracted"]["distance"] = float(dist_m.group(1))

    # 提取角度偏移
    angle_m = re.search(r"偏(左|右|上|下)\s*(\d+)\s*度", description)
    if angle_m:
        result["extracted"]["offset_direction"] = angle_m.group(1)
        result["extracted"]["offset_angle"] = float(angle_m.group(2))

    # 方位词 → 角度
    bearing_result = op_words_to_bearing(description)
    if bearing_result.get("angle_deg"):
        result["extracted"]["bearing_angle"] = bearing_result["angle_deg"]

    # 方向词 → 向量
    dir_map = {
        "前": (0, 1, 0),
        "后": (0, -1, 0),
        "左": (-1, 0, 0),
        "右": (1, 0, 0),
        "上": (0, 0, 1),
        "下": (0, 0, -1),
        "前方": (0, 1, 0),
        "后方": (0, -1, 0),
        "左方": (-1, 0, 0),
        "右方": (1, 0, 0),
        "上方": (0, 0, 1),
        "下方": (0, 0, -1),
    }
    dir_vector = None
    for word, vec in dir_map.items():
        if word in description:
            dir_vector = vec
            result["extracted"]["direction_word"] = word
            result["extracted"]["direction_vector"] = list(vec)
            break

    # 朝向角度
    facing_m = re.search(r"(?:面[朝向]|朝向)[^\d]*(\d+)\s*度", description)
    if facing_m:
        result["extracted"]["facing_angle"] = float(facing_m.group(1))

    # 生成数学表达
    math_expr = {}
    dist = result["extracted"].get("distance", 1.0)
    bearing = result["extracted"].get("bearing_angle", 0)

    if dir_vector:
        # 基本方向向量
        base = list(dir_vector)
        # 应用方位偏移
        offset = result["extracted"].get("offset_angle", 0)
        if result["extracted"].get("offset_direction") in ("左", "上"):
            offset = -offset
        # 如果既有方位又有方向词，组合
        if bearing != 0:
            bearing_rad = math.radians(bearing)
            # 在水平面旋转
            cos_b, sin_b = math.cos(bearing_rad), math.sin(bearing_rad)
            x = base[0] * cos_b - base[1] * sin_b
            y = base[0] * sin_b + base[1] * cos_b
            z = base[2]
            pos = [x * dist, y * dist, z * dist]
        else:
            pos = [base[0] * dist, base[1] * dist, base[2] * dist]
    elif bearing != 0:
        bearing_rad = math.radians(bearing)
        pos = [math.sin(bearing_rad) * dist, math.cos(bearing_rad) * dist, 0]
    else:
        pos = [0, dist, 0]

    math_expr["relative_position"] = pos
    math_expr["vector_form"] = f"({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})"

    # 极坐标
    horiz = math.sqrt(pos[0] ** 2 + pos[1] ** 2)
    math_expr["polar"] = {
        "r": math.sqrt(pos[0] ** 2 + pos[1] ** 2 + pos[2] ** 2),
        "theta_deg": math.degrees(math.atan2(pos[0], pos[1])) % 360,
        "phi_deg": math.degrees(math.atan2(pos[2], horiz)) if horiz > 0 else 0,
    }

    # 旋转矩阵（如果有朝向偏移）
    facing = result["extracted"].get("facing_angle", 0)
    if facing != 0:
        f_rad = math.radians(facing)
        cos_f, sin_f = math.cos(f_rad), math.sin(f_rad)
        math_expr["rotation_matrix_2d"] = [
            [cos_f, -sin_f, 0],
            [sin_f, cos_f, 0],
            [0, 0, 1],
        ]

    result["mathematical_expression"] = math_expr

    # 生成公式字符串
    formulas = []
    if math_expr.get("vector_form"):
        formulas.append(f"相对位置向量: {math_expr['vector_form']}")
    if math_expr.get("rotation_matrix_2d"):
        formulas.append(f"旋转矩阵: R_z({facing}°)")
    if math_expr.get("polar"):
        p = math_expr["polar"]
        formulas.append(f"极坐标: r={p['r']:.3f}, θ={p['theta_deg']:.1f}°")

    result["formulas"] = formulas

    return result


HANDEDNESS = {
    "unity": {"hand": "left", "up": "Y", "forward": "Z"},
    "unreal": {"hand": "left", "up": "Z", "forward": "X"},
    "opengl": {"hand": "right", "up": "Y", "forward": "-Z"},
    "directx": {"hand": "left", "up": "Y", "forward": "Z"},
    "3dsmax": {"hand": "right", "up": "Z", "forward": "-Y"},
    "maya": {"hand": "right", "up": "Y", "forward": "Z"},
    "blender": {"hand": "right", "up": "Z", "forward": "-Y"},
    "sword5": {"hand": "left", "up": "Y", "forward": "Z"},
}


def op_convert_point(point, from_hand, to_hand, flip="z"):
    """点在左手系和右手系之间转换（翻转Z轴）"""
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    p = np.array(_parse_vec(point), dtype=float)
    if from_hand == to_hand:
        return {"point": p.tolist(), "note": "同手系，无需转换"}
    flip_map = {"z": np.array([1, 1, -1]), "y": np.array([1, -1, 1]), "x": np.array([-1, 1, 1])}
    result = p * flip_map.get(flip, flip_map["z"])
    return {
        "original": p.tolist(),
        "converted": result.tolist(),
        "from": from_hand,
        "to": to_hand,
        "flipped_axis": flip,
        "note": f"{'左手' if from_hand == 'left' else '右手'}→{'右手' if to_hand == 'right' else '左手'}，翻转{flip.upper()}轴",
    }


def op_convert_rotation(rotation, from_hand, to_hand, format="quat", flip="z"):
    """旋转在左右手系间转换（支持四元数/欧拉角/矩阵）"""
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    if from_hand == to_hand:
        return {"rotation": rotation, "note": "同手系无需转换"}
    if format == "quat":
        q = np.array(_parse_vec(rotation), dtype=float)
        if len(q) != 4:
            return {"error": "四元数需4分量 [w,x,y,z]"}
        q = q / np.linalg.norm(q)
        w, x, y, z = q
        if flip == "z":
            qn = np.array([w, -x, -y, z])
        elif flip == "y":
            qn = np.array([w, -x, y, -z])
        else:
            qn = q
        return {
            "original_quat": q.tolist(),
            "converted_quat": (qn / np.linalg.norm(qn)).tolist(),
            "note": f"翻转{flip}轴→取反相关分量。旋转角度不变，方向可能反转",
        }
    elif format == "euler":
        r = rotation if isinstance(rotation, (list, tuple)) else _parse_vec(rotation)
        yaw, pitch, roll = r[0], r[1], r[2]
        if flip == "z":
            c = [-yaw, pitch, -roll]
        elif flip == "y":
            c = [yaw, -pitch, roll]
        else:
            c = list(r)
        return {"original_euler": list(r), "converted_euler": c, "note": f"翻转{flip}轴→取反Yaw/Roll"}


def op_convert_matrix(matrix, from_hand, to_hand, flip="z"):
    """4x4变换矩阵在左右手系间转换: M' = F * M * F"""
    if not HAS_NUMPY:
        return {"error": "需要 numpy"}
    M = np.array(matrix, dtype=float)
    if M.shape != (4, 4) and len(M.shape) == 2:
        M = M[:4, :4]
    if from_hand == to_hand:
        return {"matrix": M.tolist()}
    F = np.eye(4)
    if flip == "z":
        F[2, 2] = -1
    elif flip == "y":
        F[1, 1] = -1
    M_new = F @ M @ F
    return {
        "original_matrix": M.tolist(),
        "converted_matrix": M_new.tolist(),
        "note": f"翻转{flip}轴: F·M·F, F=diag(1,{'-1' if flip == 'y' else '1'},{'-1' if flip == 'z' else '1'},1)",
    }


def op_list_handedness():
    """列出常见引擎的坐标系约定"""
    return {
        "engines": HANDEDNESS,
        "how_to_convert": "左手↔右手 = 翻转Z轴(最常用)。点取反Z，四元数取反xy，矩阵F·M·F。",
        "cross_product_note": "左手系用左手定则(顺时针为正)，右手系用右手定则(逆时针为正)。叉积方向相反。",
        "sword5_convention": "左手系，Y轴向上，Z轴向前(DirectX风格)",
    }


OPERATIONS = {
    "describe_position": op_describe_position,
    "bearing_to_words": op_bearing_to_words,
    "words_to_bearing": op_words_to_bearing,
    "coordinate_convert": op_coordinate_convert,
    "transform": op_transform,
    "relative": op_relative,
    "describe_to_math": op_describe_to_math,
    "convert_point": op_convert_point,
    "convert_rotation": op_convert_rotation,
    "convert_matrix": op_convert_matrix,
    "list_handedness": op_list_handedness,
}


def main():
    parser = argparse.ArgumentParser(
        description="空间推理工具 — 方向/旋转/坐标系/参考系",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python spatial_sense.py --op "describe_position" --x 10 --y 5 --z 3 --observer "0,0,0"
  python spatial_sense.py --op "bearing_to_words" --angle 135
  python spatial_sense.py --op "relative" --a "0,0,0" --b "10,0,0" --a-facing 90
  python spatial_sense.py --op "transform" --point "5,0,0" --from-frame "world" --to-frame "camera" --camera-pos "10,5,3" --camera-yaw 45
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--x", type=float, default=0, help="X坐标")
    parser.add_argument("--y", type=float, default=0, help="Y坐标")
    parser.add_argument("--z", type=float, default=0, help="Z坐标")
    parser.add_argument("--observer", help="观察者位置")
    parser.add_argument("--angle", type=float, help="角度（度）")
    parser.add_argument("--desc", help="方位描述文字")
    parser.add_argument("--point", help="点坐标")
    parser.add_argument("--a", help="物体A坐标")
    parser.add_argument("--b", help="物体B坐标")
    parser.add_argument("--a-facing", type=float, default=0, help="A的朝向角度")
    parser.add_argument("--from-frame", default="world", help="源参考系")
    parser.add_argument("--to-frame", default="camera", help="目标参考系")
    parser.add_argument("--from-sys", default="cartesian", help="源坐标系")
    parser.add_argument("--to-sys", default="spherical", help="目标坐标系")
    parser.add_argument("--camera-pos", help="相机位置")
    parser.add_argument("--camera-yaw", type=float, default=0, help="相机偏航角")
    parser.add_argument("--camera-pitch", type=float, default=0, help="相机俯仰角")
    parser.add_argument("--compact", "-c", action="store_true", help="紧凑输出")
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
        print(json.dumps({"ok": False, "error": f"不支持: {op}, 可用: {list(OPERATIONS.keys())}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        kwargs = {}
        if op == "describe_position":
            kwargs["x"] = args.x if args.x is not None else input_data.get("x", 0)
            kwargs["y"] = args.y if args.y is not None else input_data.get("y", 0)
            kwargs["z"] = args.z if args.z is not None else input_data.get("z", 0)
            kwargs["observer"] = args.observer or input_data.get("observer")
        elif op == "bearing_to_words":
            kwargs["angle_deg"] = args.angle or input_data.get("angle", 0)
        elif op == "words_to_bearing":
            kwargs["desc"] = args.desc or input_data.get("desc", "")
        elif op == "coordinate_convert":
            kwargs.update({k: input_data.get(k, getattr(args, k, 0)) for k in ["x", "y", "z", "from_sys", "to_sys"]})
        elif op == "transform":
            kwargs["point_str"] = args.point or input_data.get("point", "0,0,0")
            kwargs["from_frame"] = args.from_frame or input_data.get("from_frame", "world")
            kwargs["to_frame"] = args.to_frame or input_data.get("to_frame", "camera")
            kwargs["camera_pos"] = args.camera_pos or input_data.get("camera_pos")
            kwargs["camera_yaw"] = args.camera_yaw or input_data.get("camera_yaw", 0)
            kwargs["camera_pitch"] = args.camera_pitch or input_data.get("camera_pitch", 0)
        elif op == "relative":
            kwargs["a_str"] = args.a or input_data.get("a", "0,0,0")
            kwargs["b_str"] = args.b or input_data.get("b", "0,0,0")
            kwargs["a_facing"] = args.a_facing or input_data.get("a_facing", 0)
        elif op == "describe_to_math":
            kwargs["description"] = args.desc or input_data.get("desc", "")

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
