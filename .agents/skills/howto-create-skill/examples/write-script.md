# 场景：写一个 Python 脚本

新建 `scripts/my_tool.py`，模板：

```python
"""一句话功能描述。

用法:
    python my_tool.py <参数1> <参数2>
"""
import sys

def main():
    if len(sys.argv) < 3:
        print("Usage: python my_tool.py <arg1> <arg2>", file=sys.stderr)
        sys.exit(1)

    arg1, arg2 = sys.argv[1], sys.argv[2]

    # 确定性逻辑
    result = do_something(arg1, arg2)
    print(result)

if __name__ == '__main__':
    main()
```

要点：
- 顶部 docstring 写用法
- 参数通过 `sys.argv` 传入
- 错误输出 `stderr`，正常输出 `stdout`
- 退出码 0=成功，1=失败
- 单一功能，只做一件事

## 场景：脚本之间互相调用

在 `scripts/linux/xxx.py` 中调用 `scripts/hello.py`：

```python
import subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), '..', 'hello.py'), 'world'])
```
