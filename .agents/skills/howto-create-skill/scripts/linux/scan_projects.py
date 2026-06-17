"""扫描目录，列出所有 .prj 文件。

用法:
    python scan_projects.py <目录>
"""
import glob
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python scan_projects.py <directory>", file=sys.stderr)
        sys.exit(1)

    search_dir = sys.argv[1]
    prj_files = glob.glob(os.path.join(search_dir, '**', '*.prj'), recursive=True)

    if not prj_files:
        print(f"No .prj files found in {search_dir}", file=sys.stderr)
        sys.exit(1)

    for f in sorted(prj_files):
        print(f)

if __name__ == '__main__':
    main()
