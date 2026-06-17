# 左手坐标系 vs 右手坐标系

> 游戏引擎中最常见的坐标系混淆来源。本参考涵盖识别、转换和常见陷阱。

## 一、如何区分

**用手判断**：
- 左手：拇指=X，食指=Y，中指=Z → 中指指向屏幕内（左手系）
- 右手：拇指=X，食指=Y，中指=Z → 中指指向屏幕外（右手系）

**用叉积判断**：
- 右手系：X×Y=Z（逆时针为正旋转方向）
- 左手系：X×Y=Z（顺时针为正旋转方向）

**用旋转方向判断**：
- 右手系：绕轴正方向看，逆时针旋转为正
- 左手系：绕轴正方向看，顺时针旋转为正

## 二、常见引擎对照表

| 引擎/标准 | 手系 | 上轴 | 前向 | 备注 |
|-----------|------|------|------|------|
| **Unity** | 左手 | Y | Z | X 轴向右 |
| **Unreal** | 左手 | Z | X | Y 轴向右 |
| **DirectX** | 左手 | Y | Z | 传统默认 |
| **OpenGL** | 右手 | Y | -Z | 传统默认 |
| **3ds Max** | 右手 | Z | -Y | |
| **Maya** | 右手 | Y | Z | |
| **Blender** | 右手 | Z | -Y | |
| **剑网3 (Sword5)** | **左手** | **Y** | **Z** | DirectX风格 |

## 三、转换公式

### 3.1 点坐标转换

翻转 Z 轴即可（最常用，如 OpenGL↔DirectX）：

```
右手 → 左手:  (x, y, z) → (x, y, -z)
左手 → 右手:  (x, y, z) → (x, y, -z)   // 翻转操作是对合的
```

翻转 Y 轴（如 Unity↔Unreal 需要同时处理上轴差异）：

```
右手 → 左手:  (x, y, z) → (x, -y, z)
```

### 3.2 四元数旋转转换

翻转 Z 轴时，取反 x 和 y 分量，z 保持不变：

```
q_right = (w, x, y, z)
q_left  = (w, -x, -y, z)    // 归一化后使用

// 旋转角度不变，但绕Z轴的旋转方向反转
```

翻转 Y 轴时：

```
q_right = (w, x, y, z)
q_left  = (w, -x, y, -z)
```

### 3.3 旋转矩阵转换

使用对角翻转矩阵 F：

```
M_left = F · M_right · F

其中 F = diag(1, 1, -1, 1)  // 翻转Z轴
或   F = diag(1, -1, 1, 1)  // 翻转Y轴
```

### 3.4 欧拉角转换

翻转 Z 轴（Yaw-Pitch-Roll，ZYX顺序）：

```
(yaw, pitch, roll)_left = (-yaw, pitch, -roll)
```

翻转 Y 轴：

```
(yaw, pitch, roll)_left = (yaw, -pitch, roll)
```

## 四、常见陷阱

### 4.1 叉积方向反转
```
右手系: forward = cross(right, up)      // 右手定则
左手系: forward = cross(up, right)      // 左手定则 或 直接取反
```

### 4.2 视角矩阵（View Matrix）
左手系的 LookAt 矩阵与右手系差一个 Z 轴取反。错误的 LookAt 会导致：
- 模型渲染到屏幕外
- 深度测试反转（近处被远处遮挡）

### 4.3 法线贴图
右手系的法线贴图（蓝色指向+Z）导入左手系引擎时需翻转绿色通道：
```
normal_left = (r, -g, b)   // 翻转 Y 分量
```

### 4.4 动画导入
从右手系 DCC 工具（Maya/Blender）导入左手系引擎时：
- 骨骼的 Z 轴取反
- 动画曲线的旋转分量需要转换
- 蒙皮矩阵需要重新计算

## 五、工具命令

```bash
# 列出常见引擎的坐标系约定
python spatial_sense.py --op "list_handedness"

# 点坐标转换
python spatial_sense.py --op "convert_point" --point "1,2,3" --from_hand "right" --to_hand "left" --flip "z"

# 四元数旋转转换
python spatial_sense.py --op "convert_rotation" --rotation "0.707,0,0.707,0" --from_hand "right" --to_hand "left" --format "quat"

# 欧拉角转换
python spatial_sense.py --op "convert_rotation" --rotation "30,15,0" --from_hand "right" --to_hand "left" --format "euler"

# 4x4矩阵转换
python spatial_sense.py --op "convert_matrix" --matrix "[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]" --from_hand "right" --to_hand "left"
```

## 六、Sword5 项目约定

Sword5 基于 DirectX 11（`KG3DEngineDX11`），使用**左手坐标系**：
- X 轴：向右
- Y 轴：向上
- Z 轴：向前（屏幕内）
- 正旋转方向：顺时针（绕轴正方向看）

从 3ds Max（右手系）导出模型到 Sword5 时，需要翻转 Z 轴。
