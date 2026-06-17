# 欧拉公式：被投票为"史上最美公式"

**故事**：1748年，瑞士数学家欧拉在《无穷分析引论》中发表了 $e^{i\theta} = \cos\theta + i\sin\theta$。当 $\theta = \pi$ 时，得到 $e^{i\pi} + 1 = 0$——一条公式串联了 $e, i, \pi, 1, 0$ 五个数学基本常数。

但欧拉本人可能从未写出过 $e^{i\pi}+1=0$ 这个特定形式——后世数学家从他的一般公式中推导出了这个"最美"特例。

**为什么最美**：五个常数来自五个完全不同的领域——$e$（分析）、$i$（代数）、$\pi$（几何）、$1$（算术）、$0$（哲学）——在一条等式中和平共处。

## 数学证明：三种推导方法

### 方法一：泰勒展开法（最直观）

将 $e^{i\theta}$ 在 0 处展开为麦克劳林级数：


$$
e^{i\theta} = \sum_{n=0}^{\infty} \frac{(i\theta)^n}{n!} = 1 + i\theta + \frac{(i\theta)^2}{2!} + \frac{(i\theta)^3}{3!} + \frac{(i\theta)^4}{4!} + \cdots
$$

利用 $i^2 = -1, i^3 = -i, i^4 = 1$，将实部和虚部分开：

$$\begin{aligned}
e^{i\theta} &= \left(1 - \frac{\theta^2}{2!} + \frac{\theta^4}{4!} - \frac{\theta^6}{6!} + \cdots\right) \\
            &\quad + i\left(\theta - \frac{\theta^3}{3!} + \frac{\theta^5}{5!} - \frac{\theta^7}{7!} + \cdots\right) \\
            &= \cos\theta + i\sin\theta
\end{aligned}$$

实部恰好是 $\cos\theta$ 的泰勒展开，虚部恰好是 $\sin\theta$ 的泰勒展开。

**代入 $\theta = \pi$**：$\cos\pi = -1, \sin\pi = 0$，得 $e^{i\pi} = -1$，即 $e^{i\pi} + 1 = 0$。

### 方法二：微分方程法（最严格）

定义辅助函数 $f(\theta) = e^{-i\theta}(\cos\theta + i\sin\theta)$：


$$
f'(\theta) = -ie^{-i\theta}(\cos\theta + i\sin\theta) + e^{-i\theta}(-\sin\theta + i\cos\theta)
$$

代入 $\cos\theta + i\sin\theta = e^{i\theta}$（这正是我们要证的——但可以先假设再验证），简化得 $f'(\theta) = 0$。又 $f(0) = 1 \cdot (1+0) = 1$。导数为 0 意味着 $f$ 是常数，故 $f(\theta) \equiv 1$：


$$
e^{-i\theta}(\cos\theta + i\sin\theta) = 1 \Rightarrow e^{i\theta} = \cos\theta + i\sin\theta
$$

### 方法三：极坐标几何法（最直观）

在复平面上，$z = \cos\theta + i\sin\theta$ 是单位圆上的点（模长为 1，辐角为 $\theta$）。

复数的极坐标表示：$z = re^{i\theta}$（其中 $r = |z|$，$\theta = \arg(z)$）。当 $r = 1$ 时：


$$
e^{i\theta} = \cos\theta + i\sin\theta
$$

这就是"单位圆上角度为 $\theta$ 的点"的复数表示。$e^{i\theta}$ 可以理解为"从 1 开始，在复平面上沿单位圆旋转 $\theta$ 弧度"。

**游戏启示**：在 3D 游戏中，乘以 $e^{i\theta}$ 就是旋转——复数乘法比旋转矩阵直观得多。四元数 $q = e^{\frac{\theta}{2}(xi+yj+zk)}$ 是这个思想的 3D 推广。
