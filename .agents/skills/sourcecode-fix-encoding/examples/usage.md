# 使用示例

## 示例1：按 SVN 修复当前目录改动文件

```bash
python Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py K:/Sword12/Source/Common/SO3World/Src
```

## 示例2：按备份目录批量修复（先 dry-run）

```bash
python Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py K:/Sword12/Source/Common/SO3World/Src --backup K:/bak/SO3World/Src --dry-run
python Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py K:/Sword12/Source/Common/SO3World/Src --backup K:/bak/SO3World/Src
```

## 示例3：单文件按备份修复

```bash
python Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py K:/Sword12/Source/Common/SO3World/Src/KLuaPlayer.cpp --backup K:/bak/KLuaPlayer.cpp
```

## 示例4：工具自检

```bash
python Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py --self-check
```
