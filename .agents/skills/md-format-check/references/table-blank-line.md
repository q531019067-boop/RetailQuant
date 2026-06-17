# 表格空行规范

## 错误现象

表格不渲染，或者表格与前文/后文内容粘连在一起。

## 错误原因

某些 Markdown 渲染器要求表格前后必须有空行，否则不会将 `|` 开头的行识别为表格。

## 检测方法

```bash
# 检测表格前是否有空行
grep -n "^|" file.md | while read line; do
  linenum=$(echo "$line" | cut -d: -f1)
  prevline=$((linenum - 1))
  if [ $prevline -gt 0 ]; then
    prevcontent=$(sed -n "${prevline}p" file.md")
    if [ -n "$prevcontent" ] && ! echo "$prevcontent" | grep -q "^|" && ! echo "$prevcontent" | grep -q "^$"; then
      echo "Line $linenum: table without blank line before (prev: $prevcontent)"
    fi
  fi
done

# 检测表格后是否有空行
grep -n "^|" file.md | while read line; do
  linenum=$(echo "$line" | cut -d: -f1)
  nextline=$((linenum + 1))
  if [ $nextline -le $(wc -l < file.md") ]; then
    nextcontent=$(sed -n "${nextline}p" file.md")
    if [ -n "$nextcontent" ] && ! echo "$nextcontent" | grep -q "^|" && ! echo "$nextcontent" | grep -q "^$"; then
      echo "Line $linenum: table without blank line after (next: $nextcontent)"
    fi
  fi
done
```

## 修复方法

在表格前后各添加一个空行。

## 例外情况

表格紧贴标题（`#`、`##` 等）时，标题后通常已有空行，不需要额外添加。
