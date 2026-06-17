#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编码检查和转换工具
用于检查和转换Skill目录下的文件编码为UTF-8

使用方法:
    python scripts/check_encoding.py [--fix]

参数:
    --fix: 自动将非UTF-8编码的文件转换为UTF-8

示例:
    # 仅检查编码
    python scripts/check_encoding.py
    
    # 检查并修复编码
    python scripts/check_encoding.py --fix
"""

import os
import sys
import argparse
import chardet
from pathlib import Path


def detect_encoding(file_path):
    """检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'], result['confidence']


def convert_to_utf8(file_path, original_encoding):
    """将文件转换为UTF-8编码"""
    try:
        with open(file_path, 'r', encoding=original_encoding, errors='ignore') as f:
            content = f.read()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"  转换失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='编码检查和转换工具')
    parser.add_argument('--fix', action='store_true', help='自动修复非UTF-8编码的文件')
    parser.add_argument('--path', type=str, default='.', help='要检查的目录路径（默认为当前目录）')
    args = parser.parse_args()
    
    # 获取目标目录
    if args.path == '.':
        # 如果在scripts目录下运行，返回上级目录
        base_dir = Path(__file__).parent.parent
    else:
        base_dir = Path(args.path)
    
    if not base_dir.exists():
        print(f"错误: 目录不存在 {base_dir}")
        return
    
    # 要检查的文件扩展名
    text_extensions = {'.md', '.py', '.txt', '.json', '.yaml', '.yml'}
    
    print(f"正在检查目录: {base_dir}\n")
    
    converted_files = []
    utf8_files = []
    non_utf8_files = []
    
    for file_path in base_dir.rglob('*'):
        if file_path.is_file() and file_path.suffix in text_extensions:
            try:
                encoding, confidence = detect_encoding(file_path)
                
                if encoding:
                    encoding_lower = encoding.lower()
                    if encoding_lower in ['utf-8', 'utf8']:
                        utf8_files.append(file_path.relative_to(base_dir))
                    else:
                        non_utf8_files.append((file_path.relative_to(base_dir), encoding, confidence))
                        
                        print(f"发现非UTF-8文件: {file_path.relative_to(base_dir)}")
                        print(f"  当前编码: {encoding} (置信度: {confidence:.2%})")
                        
                        if args.fix:
                            if convert_to_utf8(file_path, encoding):
                                print(f"  已转换为UTF-8")
                                converted_files.append(file_path.relative_to(base_dir))
                            else:
                                print(f"  转换失败")
                        print()
            except Exception as e:
                print(f"检查文件时出错 {file_path.relative_to(base_dir)}: {e}")
    
    # 输出汇总
    print("\n" + "="*60)
    print("检查结果汇总:")
    print("="*60)
    print(f"UTF-8编码文件: {len(utf8_files)} 个")
    print(f"非UTF-8编码文件: {len(non_utf8_files)} 个")
    
    if args.fix:
        print(f"已转换文件: {len(converted_files)} 个")
    
    if non_utf8_files and not args.fix:
        print("\n提示: 使用 --fix 参数可以自动转换这些文件为UTF-8编码")
        print("命令: python scripts/check_encoding.py --fix")
    
    # 返回退出码
    if non_utf8_files and not args.fix:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
