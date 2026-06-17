"""从 prj 文件中提取指定 Config 段的字段值。

用法:
    python extract_config.py <prj文件> <配置名> <字段名>
    python extract_config.py ZoneServer.prj Debug_X64 LibDir
"""
import configparser
import sys

def main():
    if len(sys.argv) < 4:
        print("Usage: python extract_config.py <prj_file> <config_name> <field>", file=sys.stderr)
        print("  Fields: Product, Options, Defines, ObjDir, LibDir, Libraries", file=sys.stderr)
        sys.exit(1)

    prj_file, config_name, field = sys.argv[1], sys.argv[2], sys.argv[3]

    parser = configparser.ConfigParser()
    parser.read(prj_file, encoding='utf-8')

    section = f'Config {config_name}'
    if section not in parser:
        print(f"ERROR: [{section}] not found in {prj_file}", file=sys.stderr)
        sys.exit(1)

    value = parser[section].get(field, '')
    if value:
        print(value)
    else:
        print(f"ERROR: field '{field}' not found in [{section}]", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
