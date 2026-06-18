"""列出 VS2019 已安装的版本。

用法:
    python list_vs_editions.py
"""

import os
import sys

PROGRAM_FILES = [r"C:\Program Files (x86)", r"C:\Program Files"]
EDITIONS = ["Community", "Professional", "Enterprise"]


def main():
    found = False
    for pf in PROGRAM_FILES:
        for edition in EDITIONS:
            devenv = os.path.join(pf, "Microsoft Visual Studio", "2019", edition, "Common7", "IDE", "devenv.exe")
            if os.path.isfile(devenv):
                print(edition)
                found = True

    if not found:
        print("No VS2019 editions found", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
