# 表格被代码块包裹

## 错误现象

表格内容显示为代码（等宽字体、灰色背景），而不是渲染后的表格。

## 错误原因

Markdown 表格被 ` ``` ` 标记包裹，被解析器识别为代码块而非表格。

## 错误写法

````
```
| 列1 | 列2 |
|-----|-----|
| 值1 | 值2 |
```
````

## 正确写法

````
| 列1 | 列2 |
|-----|-----|
| 值1 | 值2 |
````

## 检测方法

```bash
# 检测代码块后紧跟表格的情况
grep -n '```' file.md | while read line; do
  linenum=$(echo "$line" | cut -d: -f1)
  nextline=$((linenum + 1))
  nextcontent=$(sed -n "${nextline}p" file.md")
  if echo "$nextcontent" | grep -q "^|"; then
    echo "Line $linenum: code block contains table"
  fi
done
```

## 修复方法

移除表格前后的 ` ``` ` 标记，让表格直接暴露在正文中。
