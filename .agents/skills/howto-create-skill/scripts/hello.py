"""示例脚本：打印问候语。

用法:
    python hello.py <名字>
    python hello.py 张三
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python hello.py <name>")
        sys.exit(1)

    name = sys.argv[1]
    print(f"你好，{name}！")


if __name__ == "__main__":
    main()
