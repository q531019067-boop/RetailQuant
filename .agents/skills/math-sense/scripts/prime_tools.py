"""
素数工具集：素性检测、筛法、因数分解、最大素数生成。

用法:
    python prime_tools.py --op is_prime --n 97
    python prime_tools.py --op sieve --limit 100
    python prime_tools.py --op factor --n 2024
    python prime_tools.py --op next_prime --n 100
    python prime_tools.py --op primes_between --a 100 --b 200
    python prime_tools.py --op gcd --a 48 --b 18
    python prime_tools.py --op lcm --a 12 --b 18
    python prime_tools.py --op totient --n 60
    python prime_tools.py --op miller_rabin --n 97 --k 10
"""

import math
import random
import sys
import json

HAS_NUMPY = False
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    pass


# ====================== 素性检测 ======================

def op_is_prime(n):
    """确定性素性检测（n<10^16 时有效）。基于试除法+6k±1优化。"""
    n = int(n)
    if n < 2: return {"n": n, "is_prime": False, "reason": "小于2"}
    if n in (2, 3): return {"n": n, "is_prime": True}
    if n % 2 == 0 or n % 3 == 0: return {"n": n, "is_prime": False, "reason": f"可被{'2' if n%2==0 else '3'}整除"}
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return {"n": n, "is_prime": False, "factor": i if n % i == 0 else i+2}
        i += 6
    return {"n": n, "is_prime": True}


def op_miller_rabin(n, k=10):
    """Miller-Rabin 概率素性检测。k次测试，误判率 < 4^{-k}。"""
    n = int(n); k = int(k)
    if n < 2: return {"n": n, "is_prime": False}
    if n in (2, 3): return {"n": n, "is_prime": True, "method": "trivial"}
    if n % 2 == 0: return {"n": n, "is_prime": False, "method": "even"}

    # 写 n-1 = d * 2^s
    s, d = 0, n - 1
    while d % 2 == 0: s += 1; d //= 2

    for _ in range(k):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x == 1 or x == n - 1: continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1: break
        else:
            return {"n": n, "is_prime": False, "method": "Miller-Rabin", "witness": a, "k": k}
    return {"n": n, "is_prime": "probably", "method": "Miller-Rabin", "k": k,
            "error_bound": f"< {4**(-k):.2e}"}


# ====================== 筛法生成 ======================

def op_sieve(limit):
    """埃拉托色尼筛法：生成 [2, limit] 内所有素数。O(n log log n)。"""
    limit = int(limit)
    if limit < 2: return {"primes": [], "count": 0, "limit": limit}
    is_prime = [True] * (limit + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(limit ** 0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, limit + 1, i):
                is_prime[j] = False
    primes = [i for i, p in enumerate(is_prime) if p]
    return {"primes": primes, "count": len(primes), "limit": limit,
            "density": round(len(primes) / limit * 100, 2),
            "largest": primes[-1] if primes else None}


def op_primes_between(a, b):
    """区间 [a, b] 内的所有素数。"""
    a, b = int(a), int(b)
    if a < 2: a = 2
    result = op_sieve(b)
    primes = [p for p in result["primes"] if p >= a]
    return {"primes": primes, "count": len(primes), "range": [a, b]}


def op_next_prime(n):
    """大于 n 的下一个素数。"""
    n = int(n)
    candidate = n + 1 if n % 2 == 0 else n + 2
    while not op_is_prime(candidate)["is_prime"]:
        candidate += 2
    return {"n": n, "next_prime": candidate, "gap": candidate - n}


# ====================== 因数分解 ======================

def op_factor(n):
    """质因数分解。返回质因数列表 + 带指数的字典。"""
    n_orig = int(n)
    n = n_orig
    factors = []
    # 试除 2
    while n % 2 == 0: factors.append(2); n //= 2
    # 试除奇数
    i = 3
    while i * i <= n:
        while n % i == 0: factors.append(i); n //= i
        i += 2
    if n > 1: factors.append(n)
    # 统计指数
    exponent_map = {}
    for f in factors: exponent_map[str(f)] = exponent_map.get(str(f), 0) + 1
    latex_str = " \\cdot ".join(f"{p}^{{{e}}}" if e > 1 else str(p) for p, e in sorted(
        [(int(k), v) for k, v in exponent_map.items()]))
    return {"n": n_orig, "factors": factors, "exponents": exponent_map,
            "latex": f"${latex_str}$",
            "is_prime": len(factors) == 1}


def op_distinct_prime_factors(n):
    """不同质因数个数 ω(n)。"""
    result = op_factor(n)
    return {"n": n, "omega": len(result["exponents"]), "distinct_factors": list(result["exponents"].keys())}


# ====================== 数论函数 ======================

def op_gcd(a, b):
    """最大公约数。欧几里得算法 O(log min(a,b))。"""
    a, b = int(a), int(b)
    x, y = abs(a), abs(b)
    while y: x, y = y, x % y
    return {"a": a, "b": b, "gcd": x, "coprime": x == 1}


def op_lcm(a, b):
    """最小公倍数。lcm(a,b) = |a*b| / gcd(a,b)。"""
    g = op_gcd(a, b)["gcd"]
    return {"a": a, "b": b, "lcm": abs(int(a) * int(b)) // g, "gcd": g}


def op_totient(n):
    """欧拉 φ 函数：小于 n 且与 n 互质的正整数个数。"""
    result = op_factor(n)
    phi = n
    seen = set()
    for f in result["factors"]:
        if f not in seen: phi = phi * (f - 1) // f; seen.add(f)
    return {"n": n, "totient": phi, "formula": f"φ({n}) = {n} × " + " × ".join(
        f"(1-1/{p})" for p in seen)}


def op_primitive_root(n):
    """找模 n 的原根（n 为素数时 n 有 φ(n-1) 个原根）。"""
    n = int(n)
    if not op_is_prime(n)["is_prime"]:
        return {"error": "目前仅支持素数模的原根计算"}
    phi = n - 1
    factors = set(op_factor(phi)["factors"])
    for g in range(2, n):
        ok = True
        for q in factors:
            if pow(g, phi // q, n) == 1: ok = False; break
        if ok:
            return {"n": n, "primitive_root": g, "order": phi,
                    "meaning": f"{g} 是模 {n} 的原根——{g} 的各次幂遍历 1 到 {n-1} 所有数"}
    return {"error": "未找到原根"}


# ====================== 趣事与统计 ======================

def op_prime_facts():
    """素数趣事与已知记录。"""
    return {
        "largest_known": "2^82589933 - 1 (Mersenne prime, ~24.8 million digits, discovered 2018)",
        "twin_prime_conjecture": "存在无穷多对相差2的素数(如3和5、11和13)——未证明",
        "goldbach_conjecture": "每个大于2的偶数都可以写成两个素数之和——已验证到4×10^18, 未证明",
        "riemann_hypothesis": "ζ函数所有非平凡零点实部=1/2——未证明, Clay千禧年难题, 悬赏$1M",
        "prime_number_theorem": "小于n的素数个数 ~ n/ln(n), 由高斯和勒让德猜想, Hadamard和de la Vallée Poussin在1896年证明",
        "euclid_proof": "素数有无穷多个——欧几里得反证法: 假设有限, 构造P=Πp_i+1, P不被任何已知素数整除→矛盾",
        "largest_twin_known": "2996863034895 × 2^1290000 ± 1 (~388k digits, 2016)",
        "cunningham_chains": "形如 p, 2p+1, 4p+3... 的素数链——最长的已知链有19项",
    }


def op_prime_gaps(limit=1000):
    """计算素数间隙统计：相邻素数之差。"""
    result = op_sieve(limit)
    primes = result["primes"]
    gaps = [primes[i] - primes[i-1] for i in range(1, len(primes))]
    avg_gap = sum(gaps) / len(gaps) if gaps else 0
    max_gap = max(gaps) if gaps else 0
    return {"limit": limit, "prime_count": len(primes), "avg_gap": round(avg_gap, 2),
            "max_gap": max_gap, "max_gap_at": primes[gaps.index(max_gap)+1] if gaps else None,
            "theory_avg": f"~ln({limit}) ≈ {round(math.log(limit), 2)}",
            "gaps_sample": gaps[:20]}


OPERATIONS = {
    'is_prime': op_is_prime,
    'miller_rabin': op_miller_rabin,
    'sieve': op_sieve,
    'primes_between': op_primes_between,
    'next_prime': op_next_prime,
    'factor': op_factor,
    'distinct_factors': op_distinct_prime_factors,
    'gcd': op_gcd,
    'lcm': op_lcm,
    'totient': op_totient,
    'primitive_root': op_primitive_root,
    'prime_facts': op_prime_facts,
    'prime_gaps': op_prime_gaps,
}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='素数工具集')
    p.add_argument('--op', required=True, help='操作名称')
    p.add_argument('--n', type=int, help='整数输入')
    p.add_argument('--a', type=int, help='参数a')
    p.add_argument('--b', type=int, help='参数b')
    p.add_argument('--limit', type=int, default=100, help='上限')
    p.add_argument('--k', type=int, default=10, help='Miller-Rabin测试次数')
    args = p.parse_args()

    op = OPERATIONS.get(args.op)
    if not op:
        print(json.dumps({"error": f"未知操作: {args.op}"}))
        sys.exit(1)

    kwargs = {}
    sig = op.__code__.co_varnames[:op.__code__.co_argcount]
    if 'n' in sig and args.n is not None: kwargs['n'] = args.n
    if 'k' in sig and args.k is not None: kwargs['k'] = args.k
    if 'a' in sig and args.a is not None: kwargs['a'] = args.a
    if 'b' in sig and args.b is not None: kwargs['b'] = args.b
    if 'limit' in sig: kwargs['limit'] = args.limit

    print(json.dumps(op(**kwargs), ensure_ascii=False, indent=2))
