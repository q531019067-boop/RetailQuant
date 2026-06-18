#!/usr/bin/env python3
"""
collision_tools.py — 碰撞几何体相交/距离计算

用法:
    python collision_tools.py --op "sphere_sphere" --c1 "0,0,0" --r1 1 --c2 "2,0,0" --r2 1
    python collision_tools.py --op "ray_sphere" --ray_origin "0,0,-5" --ray_dir "0,0,1" --center "0,0,0" --radius 1
    python collision_tools.py --op "triangle_ray" --v0 "0,0,0" --v1 "1,0,0" --v2 "0,1,0" --ray_origin "0.2,0.2,-1" --ray_dir "0,0,1"
    python collision_tools.py --op "capsule_sphere" --cap_a "0,0,0" --cap_b "0,5,0" --cap_r 0.5 --sph_c "2,2,2" --sph_r 1

支持的操作 (18个):
    球体: sphere_contains_point, sphere_sphere, ray_sphere, sphere_aabb, sphere_triangle
    胶囊体: capsule_point, capsule_sphere, capsule_capsule, capsule_aabb
    AABB:  aabb_contains_point, aabb_aabb, ray_aabb
    三角形: triangle_point, triangle_ray, triangle_triangle, triangle_sphere
    椭圆:  ellipse_contains_point, ellipse_ray
    辅助:  closest_point_on_segment, segment_segment_distance, point_to_plane
"""

import sys, json, math, argparse

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _v(s):
    if isinstance(s, (list, tuple)):
        return np.array([float(v) for v in s[:3]])
    if isinstance(s, str):
        s = s.strip()
        if s.startswith("["):
            return np.array([float(v) for v in json.loads(s)[:3]])
    return np.array([float(v.strip()) for v in s.split(",")[:3]])


# ====================== 辅助函数 ======================


def _closest_point_on_segment(A, B, P):
    """点P到线段AB的最近点"""
    AB = B - A
    AP = P - A
    t = np.dot(AP, AB) / np.dot(AB, AB) if np.dot(AB, AB) > 1e-15 else 0
    t = np.clip(t, 0, 1)
    return A + t * AB, t


def _closest_point_on_triangle(v0, v1, v2, P):
    """点P到三角形的最近点（重心坐标法）"""
    v0v1 = v1 - v0
    v0v2 = v2 - v0
    N = np.cross(v0v1, v0v2)
    n_dot = np.dot(N, N)
    if n_dot < 1e-15:  # 退化三角形
        return _closest_point_on_segment(v0, v1, P)[0]
    # P在三角形平面上的投影
    v0P = P - v0
    # 检查P在三角形内的重心坐标
    d00 = np.dot(v0v1, v0v1)
    d01 = np.dot(v0v1, v0v2)
    d11 = np.dot(v0v2, v0v2)
    d20 = np.dot(v0P, v0v1)
    d21 = np.dot(v0P, v0v2)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-15:
        return v0
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1 - v - w
    if 0 <= u <= 1 and 0 <= v <= 1 and 0 <= w <= 1:
        return v0 + v * v0v1 + w * v0v2  # P投影在三角形内
    # P投影在三角形外 → 找最近的边
    candidates = [
        _closest_point_on_segment(v0, v1, P)[0],
        _closest_point_on_segment(v1, v2, P)[0],
        _closest_point_on_segment(v2, v0, P)[0],
    ]
    dists = [np.linalg.norm(c - P) for c in candidates]
    return candidates[np.argmin(dists)]


# ====================== 球体 ======================


def op_sphere_contains_point(center, radius, point):
    c, r, p = _v(center), float(radius), _v(point)
    d = np.linalg.norm(p - c)
    return {
        "contains": d <= r,
        "distance": float(d),
        "penetration": float(r - d) if d <= r else 0,
        "center": c.tolist(),
        "radius": r,
        "point": p.tolist(),
    }


def op_sphere_sphere(c1, r1, c2, r2):
    c1, c2 = _v(c1), _v(c2)
    r1, r2 = float(r1), float(r2)
    d = np.linalg.norm(c2 - c1)
    intersect = d <= r1 + r2
    return {
        "intersect": intersect,
        "distance_between_centers": float(d),
        "r1": r1,
        "r2": r2,
        "sum_radii": r1 + r2,
        "penetration": float(r1 + r2 - d) if intersect else 0,
        "contains": d + min(r1, r2) <= max(r1, r2),
    }


def op_ray_sphere(ray_origin, ray_dir, center, radius):
    o, d_vec, c, r = _v(ray_origin), _v(ray_dir), _v(center), float(radius)
    d_vec = d_vec / np.linalg.norm(d_vec)
    oc = o - c
    a = np.dot(d_vec, d_vec)
    b = 2 * np.dot(oc, d_vec)
    c_val = np.dot(oc, oc) - r * r
    disc = b * b - 4 * a * c_val
    if disc < 0:
        return {"hit": False}
    t1 = (-b - math.sqrt(disc)) / (2 * a)
    t2 = (-b + math.sqrt(disc)) / (2 * a)
    pts = []
    if t1 >= 0:
        pts.append({"t": float(t1), "point": (o + t1 * d_vec).tolist()})
    if t2 >= 0 and abs(t2 - t1) > 1e-8:
        pts.append({"t": float(t2), "point": (o + t2 * d_vec).tolist()})
    return {
        "hit": len(pts) > 0,
        "t_entry": float(t1) if t1 >= 0 else None,
        "t_exit": float(t2) if t2 >= 0 else None,
        "points": pts,
    }


def op_sphere_aabb(center, radius, aabb_min, aabb_max):
    c, r = _v(center), float(radius)
    mn, mx = _v(aabb_min), _v(aabb_max)
    closest = np.clip(c, mn, mx)
    d = np.linalg.norm(closest - c)
    return {
        "intersect": d <= r,
        "closest_point_on_aabb": closest.tolist(),
        "distance": float(d),
        "penetration": float(r - d) if d <= r else 0,
    }


def op_sphere_triangle(center, radius, v0, v1, v2):
    c, r = _v(center), float(radius)
    v0, v1, v2 = _v(v0), _v(v1), _v(v2)
    closest = _closest_point_on_triangle(v0, v1, v2, c)
    d = np.linalg.norm(closest - c)
    return {
        "intersect": d <= r,
        "closest_point": closest.tolist(),
        "distance": float(d),
        "penetration": float(r - d) if d <= r else 0,
    }


# ====================== 胶囊体 (Capsule) ======================


def op_capsule_point(cap_a, cap_b, cap_r, point):
    a, b, p = _v(cap_a), _v(cap_b), _v(point)
    r = float(cap_r)
    closest, t = _closest_point_on_segment(a, b, p)
    d = np.linalg.norm(p - closest)
    return {
        "contains": d <= r,
        "distance": float(d),
        "closest_on_axis": closest.tolist(),
        "axis_param_t": float(t),
        "penetration": float(r - d) if d <= r else 0,
    }


def op_capsule_sphere(cap_a, cap_b, cap_r, sph_c, sph_r):
    a, b, sc = _v(cap_a), _v(cap_b), _v(sph_c)
    cr, sr = float(cap_r), float(sph_r)
    closest, _ = _closest_point_on_segment(a, b, sc)
    d = np.linalg.norm(sc - closest)
    return {
        "intersect": d <= cr + sr,
        "distance": float(d),
        "sum_radii": cr + sr,
        "penetration": float(cr + sr - d) if d <= cr + sr else 0,
    }


def op_capsule_capsule(a1, b1, r1, a2, b2, r2):
    a1, b1, a2, b2 = _v(a1), _v(b1), _v(a2), _v(b2)
    r1, r2 = float(r1), float(r2)

    # 线段到线段最短距离
    def _seg_seg_dist(A, B, C, D):
        AB, CD = B - A, D - C
        AC = C - A
        d00 = np.dot(AB, AB)
        d11 = np.dot(CD, CD)
        if d00 < 1e-15:
            return np.linalg.norm(_closest_point_on_segment(C, D, A)[0] - A)
        if d11 < 1e-15:
            return np.linalg.norm(_closest_point_on_segment(A, B, C)[0] - C)
        d01 = np.dot(AB, CD)
        d10 = d01
        d20 = np.dot(AC, AB)
        d21 = np.dot(AC, CD)
        denom = d00 * d11 - d01 * d10
        if abs(denom) < 1e-15:
            t = 0
            s = np.clip(d20 / d00, 0, 1)
        else:
            s = np.clip((d01 * d21 - d11 * d20) / denom, 0, 1)
            t = np.clip((d00 * d21 - d01 * d20) / denom, 0, 1)
        p1 = A + s * AB
        p2 = C + t * CD
        return np.linalg.norm(p1 - p2)

    d = _seg_seg_dist(a1, b1, a2, b2)
    return {
        "intersect": d <= r1 + r2,
        "segment_distance": float(d),
        "sum_radii": r1 + r2,
        "penetration": float(r1 + r2 - d) if d <= r1 + r2 else 0,
    }


def op_capsule_aabb(cap_a, cap_b, cap_r, aabb_min, aabb_max):
    a, b, mn, mx = _v(cap_a), _v(cap_b), _v(aabb_min), _v(aabb_max)
    r = float(cap_r)
    # 采样胶囊轴上的点，找最近的AABB面
    n_samples = 20
    min_dist = float("inf")
    for i in range(n_samples):
        t = i / (n_samples - 1)
        pt = a + t * (b - a)
        closest = np.clip(pt, mn, mx)
        d = np.linalg.norm(closest - pt)
        if d < min_dist:
            min_dist = d
    return {
        "intersect": min_dist <= r,
        "min_distance": float(min_dist),
        "penetration": float(r - min_dist) if min_dist <= r else 0,
    }


# ====================== AABB ======================


def op_aabb_contains_point(aabb_min, aabb_max, point):
    mn, mx, p = _v(aabb_min), _v(aabb_max), _v(point)
    inside = np.all(p >= mn) and np.all(p <= mx)
    closest = np.clip(p, mn, mx)
    return {"contains": inside, "closest_point": closest.tolist(), "distance": float(np.linalg.norm(p - closest))}


def op_aabb_aabb(a1_min, a1_max, a2_min, a2_max):
    mn1, mx1, mn2, mx2 = _v(a1_min), _v(a1_max), _v(a2_min), _v(a2_max)
    overlap = np.all(mn1 <= mx2) and np.all(mn2 <= mx1)
    # 重叠量
    pen = [float(max(0, min(mx1[i], mx2[i]) - max(mn1[i], mn2[i]))) for i in range(3)]
    return {"intersect": overlap, "overlap": pen if overlap else [0, 0, 0]}


def op_ray_aabb(ray_origin, ray_dir, aabb_min, aabb_max):
    o, d_vec = _v(ray_origin), _v(ray_dir)
    mn, mx = _v(aabb_min), _v(aabb_max)
    d_vec = d_vec / max(np.linalg.norm(d_vec), 1e-15)
    t_min = float("-inf")
    t_max = float("inf")
    for i in range(3):
        if abs(d_vec[i]) < 1e-15:
            if o[i] < mn[i] or o[i] > mx[i]:
                return {"hit": False}
        else:
            t1 = (mn[i] - o[i]) / d_vec[i]
            t2 = (mx[i] - o[i]) / d_vec[i]
            t_min = max(t_min, min(t1, t2))
            t_max = min(t_max, max(t1, t2))
    if t_min > t_max:
        return {"hit": False}
    p_entry = (o + t_min * d_vec).tolist() if t_min >= 0 else None
    return {"hit": t_max >= 0, "t_entry": float(t_min), "t_exit": float(t_max), "entry_point": p_entry}


# ====================== 三角形 ======================


def op_triangle_point(v0, v1, v2, point):
    v0, v1, v2 = _v(v0), _v(v1), _v(v2)
    p = _v(point)
    closest = _closest_point_on_triangle(v0, v1, v2, p)
    d = np.linalg.norm(closest - p)
    return {"contains": d < 1e-8, "closest_point": closest.tolist(), "distance": float(d)}


def op_triangle_ray(v0, v1, v2, ray_origin, ray_dir):
    v0, v1, v2 = _v(v0), _v(v1), _v(v2)
    o, d_vec = _v(ray_origin), _v(ray_dir)
    d_vec = d_vec / np.linalg.norm(d_vec)
    e1, e2 = v1 - v0, v2 - v0
    h = np.cross(d_vec, e2)
    a = np.dot(e1, h)
    if abs(a) < 1e-10:
        return {"hit": False, "reason": "射线平行于三角形平面"}
    f = 1.0 / a
    s = o - v0
    u = f * np.dot(s, h)
    if u < 0 or u > 1:
        return {"hit": False}
    q = np.cross(s, e1)
    v = f * np.dot(d_vec, q)
    if v < 0 or u + v > 1:
        return {"hit": False}
    t = f * np.dot(e2, q)
    if t < 0:
        return {"hit": False}
    return {"hit": True, "t": float(t), "point": (o + t * d_vec).tolist(), "barycentric": [1 - u - v, u, v]}


def op_triangle_triangle(v0, v1, v2, u0, u1, u2):
    """分离轴定理(SAT)判断两个三角形是否相交"""
    v0, v1, v2 = _v(v0), _v(v1), _v(v2)
    u0, u1, u2 = _v(u0), _v(u1), _v(u2)

    def _project(tri, axis):
        dots = [np.dot(v, axis) for v in tri]
        return min(dots), max(dots)

    tri1 = [v0, v1, v2]
    tri2 = [u0, u1, u2]
    # 法向量作为分离轴
    n1 = np.cross(v1 - v0, v2 - v0)
    n2 = np.cross(u1 - u0, u2 - u0)
    # 边叉积作为分离轴
    axes = [n1, n2]
    for tri in [tri1, tri2]:
        for i in range(3):
            e = tri[(i + 1) % 3] - tri[i]
            for j in range(3):
                e2 = tri2[j] if tri is tri1 else tri1[j]
                axes.append(np.cross(e, e2 - tri[i]) if tri is tri1 else np.cross(e2 - tri[i], e))
    for axis in axes:
        if np.linalg.norm(axis) < 1e-10:
            continue
        axis = axis / np.linalg.norm(axis)
        min1, max1 = _project(tri1, axis)
        min2, max2 = _project(tri2, axis)
        if max1 < min2 or max2 < min1:
            return {"intersect": False, "separating_axis": axis.tolist()}
    return {"intersect": True}


def op_triangle_sphere(v0, v1, v2, center, radius):
    return op_sphere_triangle(center, radius, v0, v1, v2)


# ====================== 椭圆 (2D) ======================


def op_ellipse_contains_point(center, rx, ry, point, angle_deg=0):
    c = _v(center)
    p = _v(point)
    rx, ry = float(rx), float(ry)
    # 旋转到椭圆坐标系
    dp = p - c
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    x_rot = dp[0] * cos_a + dp[1] * sin_a
    y_rot = -dp[0] * sin_a + dp[1] * cos_a
    val = (x_rot / rx) ** 2 + (y_rot / ry) ** 2
    return {"contains": val <= 1, "normalized_distance": float(val)}


def op_ellipse_ray(center, rx, ry, ray_origin, ray_dir, angle_deg=0):
    """射线与椭圆求交（2D）"""
    c = _v(center)
    o = _v(ray_origin)
    d_vec = _v(ray_dir)
    rx, ry = float(rx), float(ry)
    d_vec = d_vec[:2] / np.linalg.norm(d_vec[:2])
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    # 将射线变换到椭圆局部坐标系
    oc = o[:2] - c[:2]
    ox = oc[0] * cos_a + oc[1] * sin_a
    oy = -oc[0] * sin_a + oc[1] * cos_a
    dx = d_vec[0] * cos_a + d_vec[1] * sin_a
    dy = -d_vec[0] * sin_a + d_vec[1] * cos_a
    # 解: (ox+t*dx)²/rx² + (oy+t*dy)²/ry² = 1
    a = dx * dx / (rx * rx) + dy * dy / (ry * ry)
    b = 2 * (ox * dx / (rx * rx) + oy * dy / (ry * ry))
    c_val = ox * ox / (rx * rx) + oy * oy / (ry * ry) - 1
    disc = b * b - 4 * a * c_val
    if disc < 0:
        return {"hit": False}
    t1 = (-b - math.sqrt(disc)) / (2 * a)
    t2 = (-b + math.sqrt(disc)) / (2 * a)
    pts = []
    if t1 >= 0:
        pts.append({"t": float(t1), "point": (o[:2] + t1 * d_vec[:2]).tolist()})
    if t2 >= 0 and abs(t2 - t1) > 1e-8:
        pts.append({"t": float(t2), "point": (o[:2] + t2 * d_vec[:2]).tolist()})
    return {"hit": len(pts) > 0, "points": pts}


# ====================== 辅助 ======================


def op_closest_point_on_segment(a, b, point):
    A, B, P = _v(a), _v(b), _v(point)
    closest, t = _closest_point_on_segment(A, B, P)
    return {"closest_point": closest.tolist(), "t": float(t), "distance": float(np.linalg.norm(P - closest))}


def op_segment_segment_distance(a1, b1, a2, b2):
    """两线段之间的最短距离"""
    A, B, C, D = _v(a1), _v(b1), _v(a2), _v(b2)
    AB, CD, AC = B - A, D - C, C - A
    d00 = np.dot(AB, AB)
    d11 = np.dot(CD, CD)
    d01 = np.dot(AB, CD)
    if d00 < 1e-15 and d11 < 1e-15:
        return {"distance": float(np.linalg.norm(C - A))}
    if d00 < 1e-15:
        s = 0
        t = np.clip(np.dot(AC, CD) / d11, 0, 1) if d11 > 1e-15 else 0
    elif d11 < 1e-15:
        s = np.clip(-np.dot(AC, AB) / d00, 0, 1)
        t = 0
    else:
        det = d00 * d11 - d01 * d01
        s_num = -d01 * np.dot(AC, CD) + d11 * np.dot(AC, AB)
        t_num = d00 * np.dot(AC, CD) - d01 * np.dot(AC, AB)
        if abs(det) < 1e-15:
            s = t = 0
        else:
            s = np.clip(s_num / det, 0, 1)
            t_param = np.clip(t_num / det, 0, 1)
            s = np.clip((s_num + d01 * (t_param - (t_num / det))) / d00, 0, 1)
            t = t_param
    p1 = A + s * AB
    p2 = C + t * CD
    return {
        "distance": float(np.linalg.norm(p1 - p2)),
        "closest_on_AB": p1.tolist(),
        "closest_on_CD": p2.tolist(),
        "s": float(s),
        "t": float(t),
    }


def op_point_to_plane(point, plane_point, plane_normal):
    p, pp, n = _v(point), _v(plane_point), _v(plane_normal)
    n = n / np.linalg.norm(n)
    dist = np.dot(p - pp, n)
    proj = p - dist * n
    return {
        "signed_distance": float(dist),
        "absolute_distance": float(abs(dist)),
        "projected_point": proj.tolist(),
        "side": "positive" if dist > 0 else ("negative" if dist < 0 else "on_plane"),
    }


OPERATIONS = {
    "sphere_contains_point": op_sphere_contains_point,
    "sphere_sphere": op_sphere_sphere,
    "ray_sphere": op_ray_sphere,
    "sphere_aabb": op_sphere_aabb,
    "sphere_triangle": op_sphere_triangle,
    "capsule_point": op_capsule_point,
    "capsule_sphere": op_capsule_sphere,
    "capsule_capsule": op_capsule_capsule,
    "capsule_aabb": op_capsule_aabb,
    "aabb_contains_point": op_aabb_contains_point,
    "aabb_aabb": op_aabb_aabb,
    "ray_aabb": op_ray_aabb,
    "triangle_point": op_triangle_point,
    "triangle_ray": op_triangle_ray,
    "triangle_triangle": op_triangle_triangle,
    "triangle_sphere": op_triangle_sphere,
    "ellipse_contains_point": op_ellipse_contains_point,
    "ellipse_ray": op_ellipse_ray,
    "closest_point_on_segment": op_closest_point_on_segment,
    "segment_segment_distance": op_segment_segment_distance,
    "point_to_plane": op_point_to_plane,
}


def main():
    if not HAS_NUMPY:
        print(json.dumps({"ok": False, "error": "需要 numpy"}, ensure_ascii=False))
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="碰撞几何体相交/距离计算工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python collision_tools.py --op "sphere_sphere" --c1 "0,0,0" --r1 1 --c2 "2,0,0" --r2 1
  python collision_tools.py --op "triangle_ray" --v0 "0,0,0" --v1 "1,0,0" --v2 "0,1,0" --ray_origin "0.2,0.2,-1" --ray_dir "0,0,1"
  python collision_tools.py --op "capsule_sphere" --cap_a "0,0,0" --cap_b "0,5,0" --cap_r 0.5 --sph_c "2,2,2" --sph_r 1
  python collision_tools.py --op "ellipse_contains_point" --center "0,0" --rx 2 --ry 1 --point "1,0.5"
""",
    )
    parser.add_argument("--op", "-o", help="操作名称")
    parser.add_argument("--center", help="球/椭圆中心")
    parser.add_argument("--radius", type=float, help="半径")
    parser.add_argument("--c1", "--c2", help="球体中心")
    parser.add_argument("--r1", "--r2", type=float, help="球体半径")
    parser.add_argument("--point", help="点坐标")
    parser.add_argument("--ray_origin", "--ray_dir", help="射线")
    parser.add_argument("--aabb_min", "--aabb_max", help="AABB 最小/最大点")
    parser.add_argument("--v0", "--v1", "--v2", help="三角形顶点")
    parser.add_argument("--cap_a", "--cap_b", help="胶囊端点")
    parser.add_argument("--cap_r", type=float, help="胶囊半径")
    parser.add_argument("--sph_c", help="球心")
    parser.add_argument("--sph_r", type=float, help="球半径")
    parser.add_argument("--rx", "--ry", type=float, help="椭圆半径")
    parser.add_argument("--angle", type=float, default=0, help="旋转角度(度)")
    parser.add_argument("--a", "--b", help="线段端点")
    parser.add_argument("--plane_point", "--plane_normal", help="平面点和法向量")
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
        names = ", ".join(OPERATIONS.keys())
        print(json.dumps({"ok": False, "error": f"不支持: {op}，可用: {names}"}, ensure_ascii=False))
        sys.exit(1)

    def _get(key, default=None):
        return getattr(args, key, None) or input_data.get(key, default)

    try:
        kwargs = {}
        if op == "sphere_contains_point":
            kwargs.update(center=_get("center", "0,0,0"), radius=_get("radius", 1), point=_get("point", "0,0,0"))
        elif op == "sphere_sphere":
            kwargs.update(c1=_get("c1"), r1=_get("r1"), c2=_get("c2"), r2=_get("r2"))
        elif op == "ray_sphere":
            kwargs.update(
                ray_origin=_get("ray_origin"),
                ray_dir=_get("ray_dir", "0,0,1"),
                center=_get("center", "0,0,0"),
                radius=_get("radius", 1),
            )
        elif op in ("sphere_aabb",):
            kwargs.update(
                center=_get("center"), radius=_get("radius"), aabb_min=_get("aabb_min"), aabb_max=_get("aabb_max")
            )
        elif op in ("sphere_triangle",):
            kwargs.update(center=_get("center"), radius=_get("radius"), v0=_get("v0"), v1=_get("v1"), v2=_get("v2"))
        elif op in ("capsule_point", "capsule_sphere", "capsule_capsule", "capsule_aabb"):
            kwargs.update(cap_a=_get("cap_a"), cap_b=_get("cap_b"), cap_r=_get("cap_r", 0.5))
            if op == "capsule_sphere":
                kwargs.update(sph_c=_get("sph_c"), sph_r=_get("sph_r", 1))
            elif op == "capsule_capsule":
                kwargs.update(
                    a2=_get("a2", _get("cap_a2")), b2=_get("b2", _get("cap_b2")), r2=_get("r2", _get("cap_r2", 0.5))
                )
            elif op == "capsule_aabb":
                kwargs.update(aabb_min=_get("aabb_min"), aabb_max=_get("aabb_max"))
            elif op == "capsule_point":
                kwargs.update(point=_get("point"))
        elif op in ("aabb_contains_point",):
            kwargs.update(aabb_min=_get("aabb_min"), aabb_max=_get("aabb_max"), point=_get("point"))
        elif op == "aabb_aabb":
            kwargs.update(
                a1_min=_get("aabb_min"),
                a1_max=_get("aabb_max"),
                a2_min=_get("a2_min", _get("aabb_min2")),
                a2_max=_get("a2_max", _get("aabb_max2")),
            )
        elif op == "ray_aabb":
            kwargs.update(
                ray_origin=_get("ray_origin"),
                ray_dir=_get("ray_dir"),
                aabb_min=_get("aabb_min"),
                aabb_max=_get("aabb_max"),
            )
        elif op in ("triangle_point", "triangle_ray", "triangle_sphere", "triangle_triangle"):
            kwargs.update(v0=_get("v0"), v1=_get("v1"), v2=_get("v2"))
            if op == "triangle_point":
                kwargs.update(point=_get("point"))
            elif op == "triangle_ray":
                kwargs.update(ray_origin=_get("ray_origin"), ray_dir=_get("ray_dir"))
            elif op == "triangle_sphere":
                kwargs.update(center=_get("center"), radius=_get("radius"))
            elif op == "triangle_triangle":
                kwargs.update(u0=_get("u0", _get("v3")), u1=_get("u1", _get("v4")), u2=_get("u2", _get("v5")))
        elif op in ("ellipse_contains_point", "ellipse_ray"):
            kwargs.update(
                center=_get("center", "0,0"), rx=_get("rx", 1), ry=_get("ry", 0.5), angle_deg=_get("angle", 0)
            )
            if op == "ellipse_contains_point":
                kwargs.update(point=_get("point"))
            elif op == "ellipse_ray":
                kwargs.update(ray_origin=_get("ray_origin"), ray_dir=_get("ray_dir"))
        elif op == "closest_point_on_segment":
            kwargs.update(a=_get("a"), b=_get("b"), point=_get("point"))
        elif op == "segment_segment_distance":
            kwargs.update(a1=_get("a1", _get("a")), b1=_get("b1", _get("b")), a2=_get("a2"), b2=_get("b2"))
        elif op == "point_to_plane":
            kwargs.update(
                point=_get("point"),
                plane_point=_get("plane_point", "0,0,0"),
                plane_normal=_get("plane_normal", "0,0,1"),
            )

        result = OPERATIONS[op](**kwargs)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "op": op}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
