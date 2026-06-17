#!/usr/bin/env python3
"""
vec_ops.py — 向量与矩阵运算工具

用法:
    echo '{"op":"dot","a":[1,2,3],"b":[4,5,6]}' | python vec_ops.py
    python vec_ops.py --op "cross" --a "[1,0,0]" --b "[0,1,0]"
    python vec_ops.py --op "lerp" --a "[0,0,0]" --b "[10,10,10]" --t 0.5
    python vec_ops.py --op "rotate2d" --v "[1,0]" --angle 90

支持的操作:
    dot, cross, norm, normalize, angle, distance, project, reject,
    lerp, slerp, rotate2d, rotate3d,
    mat_mul, mat_det, mat_inv, mat_transpose, mat_eigen, solve_linear
"""
import sys, json, math, argparse

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _to_array(v):
    """将输入转为 numpy 数组"""
    if isinstance(v, str):
        v = json.loads(v)
    if isinstance(v, dict):
        keys = ['x', 'y', 'z', 'w']
        v = [v.get(k, 0) for k in keys if k in v]
    return np.array(v, dtype=float)


def _to_json(obj):
    """numpy → JSON"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    return obj


def op_dot(a, b):
    a, b = _to_array(a), _to_array(b)
    return {"dot": float(np.dot(a, b))}


def op_cross(a, b):
    a, b = _to_array(a), _to_array(b)
    if len(a) == 2:
        return {"cross_2d": float(np.cross(a, b))}
    return {"cross": _to_json(np.cross(a, b))}


def op_norm(v, p=2):
    v = _to_array(v)
    return {f"L{p}_norm": float(np.linalg.norm(v, ord=p))}


def op_normalize(v):
    v = _to_array(v)
    n = np.linalg.norm(v)
    if n == 0:
        return {"normalized": _to_json(v), "warning": "零向量无法归一化"}
    return {"normalized": _to_json(v / n), "norm": float(n)}


def op_angle(a, b, unit='deg'):
    a, b = _to_array(a), _to_array(b)
    cos_theta = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    cos_theta = np.clip(cos_theta, -1, 1)
    rad = math.acos(float(cos_theta))
    if unit == 'deg':
        return {"angle_deg": math.degrees(rad), "angle_rad": rad}
    return {"angle_rad": rad}


def op_distance(a, b, metric='euclidean'):
    a, b = _to_array(a), _to_array(b)
    if metric == 'euclidean':
        d = np.linalg.norm(a - b)
    elif metric == 'manhattan':
        d = np.sum(np.abs(a - b))
    elif metric == 'chebyshev':
        d = np.max(np.abs(a - b))
    else:
        d = np.linalg.norm(a - b)
    return {"distance": float(d), "metric": metric}


def op_project(a, b):
    """a 在 b 上的投影"""
    a, b = _to_array(a), _to_array(b)
    scalar = np.dot(a, b) / np.dot(b, b)
    proj = scalar * b
    return {"projection": _to_json(proj), "scalar": float(scalar)}


def op_reject(a, b):
    """a 垂直于 b 的分量"""
    a, b = _to_array(a), _to_array(b)
    scalar = np.dot(a, b) / np.dot(b, b)
    rej = a - scalar * b
    return {"rejection": _to_json(rej)}


def op_lerp(a, b, t):
    a, b = _to_array(a), _to_array(b)
    return {"lerp": _to_json((1 - t) * a + t * b), "t": t}


def op_slerp(a, b, t):
    """球面线性插值（单位向量间）"""
    a, b = _to_array(a), _to_array(b)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    dot = np.clip(np.dot(a, b), -1, 1)
    omega = math.acos(float(dot))
    if abs(omega) < 1e-10:
        return {"slerp": _to_json(a)}
    sin_omega = math.sin(omega)
    result = (math.sin((1 - t) * omega) / sin_omega) * a + (math.sin(t * omega) / sin_omega) * b
    return {"slerp": _to_json(result), "t": t, "omega_rad": omega}


def op_rotate2d(v, angle_deg):
    v = _to_array(v)
    rad = math.radians(angle_deg)
    rot = np.array([[math.cos(rad), -math.sin(rad)], [math.sin(rad), math.cos(rad)]])
    return {"rotated": _to_json(np.dot(rot, v[:2])), "angle_deg": angle_deg}


def op_rotate3d(v, axis, angle_deg):
    """绕任意轴旋转 (Rodrigues公式)"""
    v = _to_array(v)
    axis = _to_array(axis)
    axis = axis / np.linalg.norm(axis)
    rad = math.radians(angle_deg)
    cos_t = math.cos(rad)
    sin_t = math.sin(rad)
    # Rodrigues: v_rot = v*cos + (k x v)*sin + k*(k·v)*(1-cos)
    k = axis
    result = v * cos_t + np.cross(k, v) * sin_t + k * np.dot(k, v) * (1 - cos_t)
    return {"rotated": _to_json(result), "axis": _to_json(axis), "angle_deg": angle_deg}


def op_mat_mul(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    return {"product": _to_json(np.dot(a, b))}


def op_mat_det(a):
    a = np.array(a, dtype=float)
    return {"determinant": float(np.linalg.det(a))}


def op_mat_inv(a):
    a = np.array(a, dtype=float)
    try:
        inv = np.linalg.inv(a)
        return {"inverse": _to_json(inv)}
    except np.linalg.LinAlgError:
        return {"error": "矩阵不可逆 (奇异矩阵)"}


def op_mat_transpose(a):
    a = np.array(a, dtype=float)
    return {"transpose": _to_json(a.T)}


def op_mat_eigen(a):
    a = np.array(a, dtype=float)
    w, v = np.linalg.eig(a)
    return {"eigenvalues": _to_json(w), "eigenvectors": _to_json(v)}


def op_solve_linear(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    try:
        x = np.linalg.solve(a, b)
        return {"solution": _to_json(x)}
    except np.linalg.LinAlgError:
        return {"error": "无唯一解或矩阵奇异"}


# ====================== 四元数 ======================

def op_quat_from_axis_angle(axis, angle_deg):
    """从轴角创建四元数"""
    axis = _to_array(axis)
    axis = axis / np.linalg.norm(axis)
    half = math.radians(angle_deg) / 2
    q = np.array([math.cos(half), axis[0]*math.sin(half), axis[1]*math.sin(half), axis[2]*math.sin(half)])
    return {"quaternion": _to_json(q), "axis": _to_json(axis), "angle_deg": angle_deg,
            "geometric": f"四元数将绕轴旋转{angle_deg}°编码为4个数，避免欧拉角的万向节锁。"}

def op_quat_mul(q1, q2):
    """四元数乘法（组合旋转：先q2后q1）"""
    q1, q2 = _to_array(q1), _to_array(q2)
    w1,x1,y1,z1 = q1; w2,x2,y2,z2 = q2
    w = w1*w2 - x1*x2 - y1*y2 - z1*z2
    x = w1*x2 + x1*w2 + y1*z2 - z1*y2
    y = w1*y2 - x1*z2 + y1*w2 + z1*x2
    z = w1*z2 + x1*y2 - y1*x2 + z1*w2
    return {"product": _to_json(np.array([w,x,y,z])), "geometric": "四元数乘法=旋转的复合"}

def op_quat_rotate(q, v):
    """用四元数旋转向量"""
    q, v = _to_array(q), _to_array(v)
    q = q / np.linalg.norm(q)
    w, x, y, z = q
    R = np.array([[1-2*y*y-2*z*z,2*x*y-2*w*z,2*x*z+2*w*y],
                  [2*x*y+2*w*z,1-2*x*x-2*z*z,2*y*z-2*w*x],
                  [2*x*z-2*w*y,2*y*z+2*w*x,1-2*x*x-2*y*y]])
    v3 = v[:3] if len(v) >= 3 else np.pad(v, (0,3-len(v)))
    return {"rotated": _to_json(np.dot(R, v3))}

def op_quat_slerp(q1, q2, t):
    """四元数球面线性插值（动画平滑旋转）"""
    q1, q2 = _to_array(q1), _to_array(q2)
    q1, q2 = q1/np.linalg.norm(q1), q2/np.linalg.norm(q2)
    dot = np.clip(np.dot(q1, q2), -1, 1)
    if dot < 0: q2, dot = -q2, -dot
    if dot > 0.9995:
        result = (q1 + t*(q2 - q1)); result = result / np.linalg.norm(result)
    else:
        theta_0 = math.acos(dot); theta = theta_0 * t
        s0 = math.sin(theta_0 - theta) / math.sin(theta_0)
        s1 = math.sin(theta) / math.sin(theta_0)
        result = s0*q1 + s1*q2
    return {"slerp": _to_json(result), "t": t, "geometric": "slerp在两旋转间恒定角速度插值，用于动画和相机平滑跟随。"}


# ====================== 欧拉角 ↔ 四元数 ↔ 旋转矩阵 ======================

def _euler_to_quat(yaw, pitch, roll, order='ZYX'):
    """欧拉角→四元数，支持多种旋转顺序"""
    cy = math.cos(yaw/2); sy = math.sin(yaw/2)
    cp = math.cos(pitch/2); sp = math.sin(pitch/2)
    cr = math.cos(roll/2); sr = math.sin(roll/2)
    if order == 'ZYX':  # 默认：Yaw(Z)→Pitch(Y)→Roll(X)
        w = cr*cp*cy + sr*sp*sy
        x = sr*cp*cy - cr*sp*sy
        y = cr*sp*cy + sr*cp*sy
        z = cr*cp*sy - sr*sp*cy
    elif order == 'XYZ':
        w = cr*cp*cy - sr*sp*sy
        x = sr*cp*cy + cr*sp*sy
        y = cr*sp*cy - sr*cp*sy
        z = cr*cp*sy + sr*sp*cy
    else:
        return {"error": f"不支持的旋转顺序: {order}，支持 ZYX / XYZ"}
    return {"quaternion": [w, x, y, z], "order": order,
            "yaw_deg": math.degrees(yaw), "pitch_deg": math.degrees(pitch), "roll_deg": math.degrees(roll)}


def _quat_to_euler(q, order='ZYX'):
    """四元数→欧拉角"""
    q = _to_array(q); q = q / np.linalg.norm(q)
    w, x, y, z = q
    if order == 'ZYX':
        # Roll (x-axis rotation)
        sinr_cosp = 2*(w*x + y*z)
        cosr_cosp = 1 - 2*(x*x + y*y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        # Pitch (y-axis rotation)
        sinp = 2*(w*y - z*x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi/2, sinp)
        else:
            pitch = math.asin(sinp)
        # Yaw (z-axis rotation)
        siny_cosp = 2*(w*z + x*y)
        cosy_cosp = 1 - 2*(y*y + z*z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
    else:
        return {"error": f"不支持的旋转顺序: {order}"}
    return {"yaw_deg": math.degrees(yaw), "pitch_deg": math.degrees(pitch), "roll_deg": math.degrees(roll),
            "yaw_rad": yaw, "pitch_rad": pitch, "roll_rad": roll,
            "gimbal_lock": abs(abs(sinp) - 1) < 1e-6 if 'sinp' in dir() else False,
            "warning": "pitch≈±90°时出现万向节锁——yaw和roll不可区分" if abs(abs(
                (2*(w*y - z*x) if order=='ZYX' else 0)) - 1) < 1e-6 else ""}


def _euler_to_matrix(yaw, pitch, roll, order='ZYX'):
    """欧拉角→3x3旋转矩阵"""
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    if order == 'ZYX':
        R = Rz @ Ry @ Rx
    elif order == 'XYZ':
        R = Rx @ Ry @ Rz
    else:
        return {"error": f"不支持的旋转顺序: {order}"}
    return {"matrix": _to_json(R), "order": order}


def _matrix_to_quat(R):
    """3x3旋转矩阵→四元数"""
    R = np.array(R, dtype=float).reshape(3, 3)
    trace = np.trace(R)
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2,1] - R[1,2]) * s
        y = (R[0,2] - R[2,0]) * s
        z = (R[1,0] - R[0,1]) * s
    elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
        s = 2.0 * math.sqrt(1.0 + R[0,0] - R[1,1] - R[2,2])
        w = (R[2,1] - R[1,2]) / s
        x = 0.25 * s
        y = (R[0,1] + R[1,0]) / s
        z = (R[0,2] + R[2,0]) / s
    elif R[1,1] > R[2,2]:
        s = 2.0 * math.sqrt(1.0 + R[1,1] - R[0,0] - R[2,2])
        w = (R[0,2] - R[2,0]) / s
        x = (R[0,1] + R[1,0]) / s
        y = 0.25 * s
        z = (R[1,2] + R[2,1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + R[2,2] - R[0,0] - R[1,1])
        w = (R[1,0] - R[0,1]) / s
        x = (R[0,2] + R[2,0]) / s
        y = (R[1,2] + R[2,1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    return {"quaternion": _to_json(q / np.linalg.norm(q))}


def op_euler_to_quat(yaw, pitch, roll, order='ZYX'):
    y, p, r = math.radians(yaw), math.radians(pitch), math.radians(roll)
    return _euler_to_quat(y, p, r, order)

def op_quat_to_euler(q, order='ZYX'):
    return _quat_to_euler(q, order)

def op_euler_to_matrix(yaw, pitch, roll, order='ZYX'):
    y, p, r = math.radians(yaw), math.radians(pitch), math.radians(roll)
    return _euler_to_matrix(y, p, r, order)

def op_matrix_to_quat(R):
    return _matrix_to_quat(R)


OPERATIONS = {
    'dot': op_dot, 'cross': op_cross, 'norm': op_norm,
    'normalize': op_normalize, 'angle': op_angle, 'distance': op_distance,
    'project': op_project, 'reject': op_reject,
    'lerp': op_lerp, 'slerp': op_slerp,
    'rotate2d': op_rotate2d, 'rotate3d': op_rotate3d,
    'mat_mul': op_mat_mul, 'mat_det': op_mat_det,
    'mat_inv': op_mat_inv, 'mat_transpose': op_mat_transpose,
    'mat_eigen': op_mat_eigen, 'solve_linear': op_solve_linear,
    'quat_from_axis_angle': op_quat_from_axis_angle, 'quat_mul': op_quat_mul,
    'quat_rotate': op_quat_rotate, 'quat_slerp': op_quat_slerp,
    'euler_to_quat': op_euler_to_quat, 'quat_to_euler': op_quat_to_euler,
    'euler_to_matrix': op_euler_to_matrix, 'matrix_to_quat': op_matrix_to_quat,
}


def main():
    if not HAS_NUMPY:
        print(json.dumps({"ok": False, "error": "需要安装 numpy: pip install numpy"}, ensure_ascii=False))
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="向量与矩阵运算工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  echo '{"op":"dot","a":[1,2,3],"b":[4,5,6]}' | python vec_ops.py
  python vec_ops.py --op "lerp" --a "[0,0]" --b "[10,10]" --t 0.5
  python vec_ops.py --op "rotate2d" --v "[1,0]" --angle 90
        """
    )
    parser.add_argument('json_input', nargs='?', help='JSON 输入')
    parser.add_argument('--op', '-o', help='操作名称')
    parser.add_argument('--a', help='向量/矩阵 A (JSON)')
    parser.add_argument('--b', help='向量/矩阵 B (JSON)')
    parser.add_argument('--v', help='向量 V (JSON)')
    parser.add_argument('--t', type=float, help='插值参数')
    parser.add_argument('--angle', type=float, help='角度（度）')
    parser.add_argument('--axis', help='旋转轴 (JSON)')
    parser.add_argument('--p', type=float, default=2, help='范数阶数')
    parser.add_argument('--unit', choices=['deg', 'rad'], default='deg', help='角度单位')
    parser.add_argument('--compact', '-c', action='store_true', help='紧凑输出')

    args = parser.parse_args()

    # 解析输入
    input_data = {}
    if args.json_input:
        input_data = json.loads(args.json_input)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            input_data = json.loads(raw)

    op = args.op or input_data.get('op', '')
    if not op or op not in OPERATIONS:
        names = ', '.join(OPERATIONS.keys())
        print(json.dumps({"ok": False, "error": f"不支持的操作: {op}，可用: {names}"}, ensure_ascii=False))
        sys.exit(1)

    try:
        # 构建参数
        params = {}
        for key in ['a', 'b', 'v']:
            if hasattr(args, key):
                val = getattr(args, key) or input_data.get(key)
                if val:
                    params[key] = _to_array(val)

        if args.t is not None or 't' in input_data:
            params['t'] = args.t if args.t is not None else input_data['t']
        if args.angle is not None or 'angle' in input_data:
            params['angle_deg'] = float(args.angle or input_data.get('angle', 0))
        if args.axis or 'axis' in input_data:
            params['axis'] = _to_array(args.axis or input_data['axis'])
        if 'p' in input_data:
            params['p'] = input_data['p']
        else:
            params['p'] = args.p
        if 'unit' in input_data:
            params['unit'] = input_data['unit']

        result = OPERATIONS[op](**params)
        output = {"ok": True, "op": op, **result}
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2, default=str))
    except Exception as e:
        output = {"ok": False, "error": str(e), "op": op}
        print(json.dumps(output, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
