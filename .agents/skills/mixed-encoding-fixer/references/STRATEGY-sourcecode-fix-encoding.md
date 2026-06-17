## 策略 1：sourcecode-fix-encoding（源码 + SVN/backup）

当目标是 `Source/` 下的源代码（`.cpp/.h/.c/.hpp` 等）并且问题主要表现为“编码/注释乱码”时，使用本策略。

### 执行规则

1. **优先确认修复基准**
   - 有可靠备份时优先 `--backup`
   - 无备份时使用 SVN 模式（工具会以 `svn cat` 的内容作为参考）
2. 批量修复前先做一次 `--dry-run`，先看命中数量与日志
3. 只处理用户指定范围，避免默认全仓扫描
4. 修复后建议抽样检查：
   - 是否仍有 `U+FFFD`（锟… 之类替换字符）
   - 是否引入新的 `???` 注释
   - 是否误改非注释代码
5. 若 `svn` 不可用，必须切换 `--backup` 模式
6. 关键目录先备份或确保可回滚（SVN/本地副本）

### 用法（SVN / 备份 / 预览 / 自检）

```bash
# 1) SVN 模式：处理目录或单文件
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" source-fix "K:/Sword11/Source/Common/SO3World/Src"
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" source-fix "K:/Sword11/Source/Common/SO3World/Src/KLuaConstList.cpp"

# 2) 备份模式：以备份目录/文件作为参考
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" source-fix "K:/Sword11/Source/Common/SO3World/Src" --backup "K:/bak/SO3World/Src"

# 3) 仅预览（不落盘）
python "<SKILL_ROOT>/scripts/mixed_encoding_tool.py" source-fix "K:/Sword11/Source/Common/SO3World/Src" --backup "K:/bak/SO3World/Src" --dry-run

# 4) 工具自检
python "Source/Tools/AITools/SKILLS/sourcecode-fix-encoding/scripts/fix_encoding.py" --self-check
```

