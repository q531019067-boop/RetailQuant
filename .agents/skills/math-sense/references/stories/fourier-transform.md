# 傅里叶：从热传导到现代信号处理

**前因**：约瑟夫·傅里叶（1768-1830）年轻时想当神父，后来成为拿破仑的官员。随拿破仑远征埃及期间，开始研究热传导问题。

**发现**：1807年，他提出一个惊人的想法：**任何函数都可以表示为三角函数的无穷级数**。数学界一片哗然——拉格朗日等大师强烈反对，认为"数学上不严格"。傅里叶坚持发表，最终被证明正确（需一些技术条件）。

**为什么革命性**：复杂的东西可以分解为简单东西的叠加——这不只是数学技巧，而是一种世界观。白光通过棱镜分解为七色光谱——傅里叶变换就是数学上的"棱镜"。

## 数学证明：从傅里叶级数到 FFT

### 1. 三角函数系的正交性

核心基础：在 $[-\pi, \pi]$ 上，三角函数系 $\{1, \cos x, \sin x, \cos 2x, \sin 2x, \ldots\}$ 构成正交基：


$$
\int_{-\pi}^{\pi} \sin(mx)\sin(nx)\,dx = \pi \cdot \delta_{mn}
$$


$$
\int_{-\pi}^{\pi} \cos(mx)\cos(nx)\,dx = \pi \cdot \delta_{mn} \quad (m,n > 0)
$$


$$
\int_{-\pi}^{\pi} \sin(mx)\cos(nx)\,dx = 0
$$

其中 $\delta_{mn}$ 是克罗内克 δ（$m=n$ 时为 1，否则为 0）。这意味着不同频率的三角函数在完整周期上"相互垂直"。

### 2. 傅里叶级数

任意周期为 $2\pi$ 的平方可积函数 $f(x)$ 可展开为：


$$
f(x) = \frac{a_0}{2} + \sum_{n=1}^{\infty} \left( a_n \cos(nx) + b_n \sin(nx) \right)
$$

系数由正交性求出（将等式两边分别乘以 $\cos(kx)$ 或 $\sin(kx)$ 并积分）：


$$
a_n = \frac{1}{\pi} \int_{-\pi}^{\pi} f(x) \cos(nx)\,dx, \quad n \geq 0
$$


$$
b_n = \frac{1}{\pi} \int_{-\pi}^{\pi} f(x) \sin(nx)\,dx, \quad n \geq 1
$$

**几何意义**：$a_n$ 和 $b_n$ 就是 $f(x)$ 在"坐标轴" $\cos(nx)$ 和 $\sin(nx)$ 上的投影长度——类比三维空间中向量 $\vec{v}=x\hat{i}+y\hat{j}+z\hat{k}$，系数就是坐标分量。

### 3. 复数形式的傅里叶级数（更优雅）

用欧拉公式 $e^{i\theta} = \cos\theta + i\sin\theta$ 统一正余弦：


$$
f(x) = \sum_{n=-\infty}^{\infty} c_n \, e^{inx}, \quad c_n = \frac{1}{2\pi} \int_{-\pi}^{\pi} f(x)\, e^{-inx}\,dx
$$

复数系数 $c_n$ 同时包含幅度 $|c_n|$ 和相位 $\arg(c_n)$ 信息。

### 4. 连续傅里叶变换

将周期推向无穷（$T \to \infty$），求和变为积分：


$$
\hat{f}(\omega) = \int_{-\infty}^{\infty} f(t)\, e^{-i\omega t}\,dt \quad\text{（正变换：时域→频域）}
$$


$$
f(t) = \frac{1}{2\pi} \int_{-\infty}^{\infty} \hat{f}(\omega)\, e^{i\omega t}\,d\omega \quad\text{（逆变换：频域→时域）}
$$

### 5. 离散傅里叶变换（DFT）

实际计算中只能处理离散采样。$N$ 个采样点 $x_0, x_1, \ldots, x_{N-1}$：


$$
X_k = \sum_{n=0}^{N-1} x_n \cdot e^{-i 2\pi k n / N}, \quad k = 0, 1, \ldots, N-1
$$

**计算复杂度**：直接计算 DFT 需要 $O(N^2)$ 次乘法——对 $N=10^6$ 这是 $10^{12}$ 次运算，不可行。

### 6. 快速傅里叶变换（FFT）——库利-图基算法

FFT 利用 $e^{-i 2\pi k n / N}$ 的周期性和对称性，将 $N$ 点 DFT 递归分解为两个 $N/2$ 点的 DFT：


$$
X_k = \sum_{n \text{ 偶数}} x_n \cdot e^{-i 2\pi k n / N} + \sum_{n \text{ 奇数}} x_n \cdot e^{-i 2\pi k n / N}
$$


$$
= E_k + e^{-i 2\pi k / N} \cdot O_k
$$

其中 $E_k$ 是偶数下标序列的 DFT，$O_k$ 是奇数下标序列的 DFT。递归分解将复杂度降为 **$O(N \log N)$**——对 $N=10^6$，从 $10^{12}$ 降到约 $2 \times 10^7$，快 50000 倍。

**这就是"改变世界的算法"的数学本质**——不是新的数学原理，而是巧妙的计算重组。

## 与游戏的连接

- Boss 技能循环分析：时间序列 → FFT → 频谱揭示隐藏周期
- 网络延迟周期检测：延迟数据的频域分析
- DPS 节奏分析：伤害输出的频谱 → 识别最优技能循环
- 音频处理：游戏音效的频谱分析、压缩、降噪

> 工具：`series_tools.py --op fft --data "[...]"` 直接计算 FFT
